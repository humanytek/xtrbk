# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import http, tools, exceptions, _

_logger = logging.getLogger(__name__)
from odoo.http import request
import json


class ShopifyOdooInventorySynchronisation(http.Controller):

    # @http.route(["/test_post_result"], type='json', auth="public", methods=['POST'], csrf=False)
    # def test_post_shopify(self, **post):
    #     _logger.info("Post request received from Shopify")
    #     _logger.info("Creating sale order...")
    #     print(post)

    @http.route(["/odoo_shopify_synchronisation"], type='json', auth="public", methods=['POST'], csrf=False)
    def synchronise_odoo(self, **post):
        _logger.info("Post request received from Shopify")
        _logger.info("Creating sale order...")
        # get the partner, if not found create new one with the given id
        try:
            if not request.httprequest.get_data():
                _logger.info("No data found, Abort")
            converted_data = json.loads(request.httprequest.get_data().decode('utf-8'))
            data = converted_data
            if not data:
                _logger.info("No data found, Abort")
                return
            
            # Search and get  ID sale order Shopify
            sale_order_id = data.get('id');
            # Search on Odoo and exit if exists
            sale_order_odoo = request.env['sale.order'].sudo().search([('shopify_sale_order_id', '=', sale_order_id)])
            if sale_order_odoo.exists():
                _logger.info("Duplicated Order, exiting right now...")
                return
          
        
            partner_shopify_id = data.get('customer')
            partner_billing_address = data.get('billing_address')
            partner_shipping_address = data.get('shipping_address')
            
            shopify_note = data.get("note") or ""
            shopify_note = "Nota de Envio: " + shopify_note;

            phone_customer = partner_shopify_id.get('default_address').get('phone')
            
            if not partner_shopify_id:
                _logger.info("Partner not found in the post json, Abort")
                return
            partner_odoo = request.env['res.partner'].sudo().search(
                [('shopify_client_id', '=', partner_shopify_id.get('id'))])
            
            if partner_odoo.exists():
                partner = partner_odoo
                partner.over_credit = True
                partner.phone = phone_customer
            else:
                _logger.info("Customer not found at the database, creating new one ...")
                partner = request.env['res.partner'].sudo().create(
                    {'name': partner_shopify_id.get('first_name') + " " + partner_shopify_id.get('last_name'),
                     'shopify_client_id': partner_shopify_id.get('id'),
                     'vat': partner_billing_address.get('company'),
                     'email': partner_shopify_id.get('email'),
                     'street_name': partner_billing_address.get('address1'),
                     'zip': partner_billing_address.get('zip'),
                     'city': partner_billing_address.get('city'),
                     'phone': phone_customer
                    })
                
                # ultimo_consumidor_tag = request.env['marvelfields.clasificaciones'].sudo().search([('name','=', 'Shopify UC')])
                # shopify_tag = request.env['marvelfields.subclases'].sudo().search([('name','=','Shopify')]) 
                
                # partner.clasificaciones_ids = [(4, ultimo_consumidor_tag.id)]
                # partner.subclases_ids = [(4, shopify_tag.id)]
                partner.ncliente = partner_shopify_id.get('id')
            
            # Custom code to be able to change the vat and address after the client has been already been registered
            # partner.vat         = partner_billing_address.get('company')
            # partner.email       = partner_shopify_id.get('email')
            # partner.street_name = partner_shipping_address.get('address1')
            # partner.zip         = partner_shipping_address.get('zip')
            # partner.city        = partner_shipping_address.get('city')
            
            # get the sale lines

            # Creating A delivery Address
            # Las direcciones son res.partner
            # Es necesario volver a crear otro res.partner diferentes para tener ambos valores.
            # Relación many2one es directo.
            billing_address_odoo = request.env['res.partner'].sudo().create(
                {
                    'name': partner_billing_address.get('first_name') + " " + partner_billing_address.get('last_name'),
                    'vat': partner_billing_address.get('company'),
                    'email': partner_shopify_id.get('email'),
                    'street_name': partner_billing_address.get('address1'),
                    'zip': partner_billing_address.get('zip'),
                    'city': partner_billing_address.get('city'),
                    'phone': phone_customer
                })
            shipping_title = "Recoger en Tienda"

            if partner_shipping_address != None :
                if partner_billing_address.get("first_name") == partner_shipping_address.get("first_name") and partner_billing_address.get("address1") == partner_shipping_address.get("address1"):
                    shipping_address_odoo = billing_address_odoo
                else:
                    shipping_address_odoo = request.env['res.partner'].sudo().create(
                    {
                        'name':  partner_shipping_address.get('first_name') + " " + partner_shipping_address.get('last_name'),
                        'vat': partner_shipping_address.get('company'),
                        'street_name': partner_shipping_address.get('address1'),
                        'zip': partner_shipping_address.get('zip'),
                        'city': partner_shipping_address.get('city'),
                    })
                
                shopify_shipping_lines = data.get('shipping_lines')
                
                if shopify_shipping_lines:
                    shipping_title = shopify_shipping_lines[0].get('title')
            else: 
                shipping_address_odoo = billing_address_odoo
            # Creating a invoice address
            # Las direcciones son res.partner
            # Es necesario volver a crear otro res.partner diferentes para tener ambos valores.
            # Relación many2one es directo.
            

            order_line_shopify = data.get('line_items')
            subtotal_without_taxes_shopify = float(data.get('subtotal_price')) - float(data.get('total_tax'))
            discount = self.get_discount_order_line_data(order_line_shopify, subtotal_without_taxes_shopify);

            if order_line_shopify:
                order_line = self.get_sale_order_line_data(order_line_shopify, discount)
                if shipping_title == 'Envío a todo México':
                    order_line = self.get_shipping_order_line(order_line)
            else:
                order_line = []
            
            it_was_gift_card = False
            for gateway_name in data.get('payment_gateway_names'):
                if gateway_name == 'gift_card':
                    it_was_gift_card = True

            sale_order = request.env['sale.order'].sudo().create(
                {
                    'partner_id': partner.id,
                    'partner_invoice_id': billing_address_odoo.id,
                    'partner_shipping_id': shipping_address_odoo.id,
                    'order_line': order_line,
                    'shopify_number': 'Shopify ' + data.get('name'),
                    'metodo_de_pago': data.get('gateway'),
                    'metodo_de_envio_shopify': shipping_title,
                    'shopify_sale_order_id': sale_order_id
                }, )
            _logger.info("Confirming the created sale")
            
            # display_name 
            # sales_team = request.env['crm.team'].sudo().search([('name', '=', 'Shopify Bolder')])
            # if sales_team.exists(): 
            #     sale_order.team_id = sales_team.id
            # else:
            #     _logger.info("Not found Shopify on sales team (crm.team)")


            sale_order.message_post(body=shopify_note)
            
            try:
                sale_order.action_confirm()
            except Exception as e:
                _logger.info("Error occurred while confirming the sale %s" % e)

            # CONFIRMA ORDEN CUANDO ENTRA
            picking_id = request.env['stock.picking'].sudo().search([('sale_id', '=', sale_order.id)], limit=1)
            if picking_id:
                _logger.info("Created stock picking of the created sale")
                for move in picking_id.move_ids_without_package:
                    move.quantity_done = move.product_uom_qty
                try:
                    _logger.info("Validating the stock picking")
                    picking_id.button_validate()

                except Exception as e:
                    _logger.info("Error occurred while validating the move %s" % e)
            else:
                _logger.info("No stock picking created for the sale")
        except Exception as e:
            _logger.info("Error occurred while executing the logic %s" % e)

    def get_shipping_order_line(self, order_line_data):
        product_id = request.env['product.product'].sudo().search([('default_code', '=', 'ENV-SHOPI')], limit=1)
        if product_id:
            order_line_data.append((0,0, {'product_id': product_id.id, 'product_uom_qty': 1}))
        else: 
            _logger.info("Shipping product not found")
        return order_line_data


    def get_sale_order_line_data(self, order_line_data, discount):
        res = []
        for line in order_line_data:
            product_id = request.env['product.product'].sudo().search([('default_code', '=', line['sku'])], limit=1)
            if product_id:
                res.append((0, 0, {'product_id': product_id.id, 'product_uom_qty': line.get('quantity'), 'discount': discount }))
        return res

    def get_discount_order_line_data(self, order_line_data, shopify_total):
        total_tax_not_included = float(0)
        discount = float(0)
        for line in order_line_data:
            product_odoo = request.env['product.product'].sudo().search([('default_code', '=', line['sku'])], limit=1)
            if product_odoo:
                total_tax_not_included += float(product_odoo.list_price) * int(line.get('quantity'))
        
        _logger.info("Shopify Total: %f" % shopify_total)
        _logger.info("Odoo Estimate: %f" % total_tax_not_included)

        if shopify_total < total_tax_not_included:
            discount = (1 - (shopify_total / total_tax_not_included )) * 100
            _logger.info("A discount it must be in the line order. Discount: %f" % discount)
        return discount

        

class ShopifyOdooProductUploadResponse(http.Controller):

    @http.route(["/shopify_product_upload_results"], type='json', auth="public", methods=['POST'], csrf=False)
    def synchronise_odoo(self, **post):
        _logger.info("Post request received from a response of product upload")
        try:
            if not request.httprequest.get_data():
                _logger.info("No data found, Abort")
            converted_data = json.loads(request.httprequest.get_data().decode('utf-8'))
            error = converted_data.get('error')
            if error:
                if error.get('status'):
                    _logger.info("Response with an error: %s" % error.get('errorMessage'))
                    return
            data = converted_data.get('payload')
            if not data:
                _logger.info("No data found, Abort")
                return

            product_template_id = self.get_product_template(data)
            if product_template_id:
                _logger.info("Found product template by the name %s" % product_template_id.name)
                product_template_id.shopify_product_id = data.get('shopify_product_id')
                response_variants = data.get('variants')
                for response_variant in response_variants:
                    if response_variant.get('sku'):
                        _logger.info("Iterating variants:")
                        for variant in product_template_id.product_variant_ids:
                            _logger.info("Im searching in variants")
                            if variant.default_code == response_variant['sku']:
                                variant.shopify_variant_id = response_variant.get('variant_id')
                                variant.shopify_inventory_item_id = response_variant.get('inventory_item_id')
                                break

        except Exception as e:
            _logger.info("Error occurred while executing the logic %s" % e)

    def get_product_template(self, data):
        # since all the variants will have the same template,
        # we need tp take only the first variant and search for it, and get its
        # template
        if data.get('variants'):
            first_variant = data['variants'][0]
            if first_variant.get('sku'):
                variant_id = request.env['product.product'].sudo().search([('default_code', '=', first_variant['sku'])],
                                                                          limit=1)
                if variant_id:
                    product_template_id = variant_id.product_tmpl_id
                    return product_template_id
