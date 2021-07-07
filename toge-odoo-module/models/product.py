from odoo import models, fields, api, _
import requests
import json
import logging

_logger = logging.getLogger(__name__)
todo_move_states = ['waiting', 'confirmed', 'assigned', 'partially_available']

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    shopify_product_id = fields.Char()
    shopify_marca = fields.Char(string="Shopify Marca")
    shopify_desc = fields.Html(string="Shopify Description")

    # def get_product_parent_tags(self):
    #     res_categ = []
    #     for categs in self.public_categ_ids:
    #         res_categ.append(categs.display_name.split('/'))
    #     if res_categ:
    #         if len(res_categ) <= 1:
    #             res_categ = res_categ[0]

    #     return res_categ

    def get_shopify_data_upload(self):
        _logger.info(_("Started getting data of the product %s") % self.name)
        variants = self.product_variant_ids
        product_image = ''
#        table_image = ''
        if self.image_1024:
            product_image = self.image_1024.decode('utf-8')
#        if self.x_studio_image_shopify:
#            table_image = self.x_studio_image_shopify.decode('utf-8')
        shopify_data_post = {
            "title": self.name,
            "vendor": self.shopify_marca if self.shopify_marca else "",
            "shopify_product_id": self.shopify_product_id,
            "description": self.shopify_desc if self.shopify_desc else "",
#            "tags": self.get_product_parent_tags(),
            "category":self.categ_id.display_name,
            "images": product_image,
#            "table_image": table_image,
#            "is_published": self.x_studio_website_shopify,
            "variants": [
                {
                    "sku": variant.default_code,
                    "variant_data": [{variant_attribute.attribute_id.display_name: variant_attribute.name} for
                                     variant_attribute in
                                     variant.product_template_attribute_value_ids],
                    "stock": variant.qty_available,
                    "sales_price": variant.list_price,
                    "barcode": variant.barcode,
                    "taxable": bool(variant.taxes_id),
                    "shopify_variant_id": variant.shopify_variant_id,
                    "inventory_item_id": variant.shopify_inventory_item_id
                } for variant in variants
            ]
        }
        return shopify_data_post

    def upload_product_to_shopify(self):
        for line in self:
            upload_data = line.get_shopify_data_upload()
            _logger.info(("upload data %s") % upload_data)
            if upload_data:
                headers = {'Content-Type': 'application/json'}
                data_json = json.dumps({'params': upload_data})
                
                try:
                    shopify_product_upload_url = self.env.user.company_id.shopify_product_upload_url
                    _logger.info(_("url %s") % shopify_product_upload_url)
                    _logger.info(_("data %s") % data_json)
                    _logger.info(_("headers %s") % headers)
                    requests.post(url=shopify_product_upload_url, data=data_json, headers=headers)
                except Exception as e:
                    _logger.error(
                        "Failed to send post request to shopify for upload the product %s, reason : %s" % (
                            line.name, e))
            else:
                _logger.error(_("The upload data is empty for the product %s") % (line.name))


class ProductProduct(models.Model):
    _inherit = 'product.product'

    shopify_variant_id = fields.Char(string="Shopify variant_id")
    shopify_inventory_item_id = fields.Char(string="Shopify inventory_item_id")

    @api.model
    def send_reservation_data_to_webserver(self):
        # Waring, this function requires an automated function to work
        # values of the automated function (name : "Any name",Model : Stock move (stock.move) ,
        # Trigger condition : On update, action to do : Execute python code, python code
        # record.product_id.with_context(updated_stock_move_qty=True, stock_move_id=record).send_reservation_data_to_webserver()
        # )
        # Making sure that the action is executed from automated action
        _logger.info("Triggered automated actions")

        if not self.env.context.get('updated_stock_move_qty'):
            return
        # Getting the stock move that's updated to see if we need to send post request
        # of virtual quantity
        stock_move_id = self.env.context.get('stock_move_id')
        if not stock_move_id:
            return
        if self.env.context.get('old_values'):
            old_values = self.env.context['old_values']
            # the virtual quantity of the product is calculated from stock.move (Stock moves).
            # Everything depends on the key old_values of the stock move, this key shows the old values of the stock
            # move before modification.
            # the following cases will provoke sending post request with the virtual quantity of the product
            # 1) if the state of the stock move changed from none reserving state ('draft','cancel','done')
            #    to a reserving state ('waiting', 'confirmed', 'assigned', 'partially_available')
            # 2) if the state of the stock move changed from reserving state to none reserving state
            # 3) if the product_qty of the stock_move changed, and the stock move was reserving state
            # 4) if the product_id of the stock_move changed , and the stock move was in reserving state (this will send
            #    the post request of the old and new product_id)

            if old_values.get(stock_move_id.id):
                stock_move_old_state = old_values[stock_move_id.id].get('state') or stock_move_id.state
                stock_move_current_state = stock_move_id.state
                old_product_qty = old_values[stock_move_id.id].get('product_qty', 'qty_unchanged')
                old_product_id = old_values[stock_move_id.id].get('product_id', 'product_unchanged')
                if old_product_qty != 'qty_unchanged':
                    old_product_qty = 'qty_changed'
                if old_product_id != 'product_unchanged':
                    old_product_id = self.env['product.product'].browse(old_product_id[0])

                if stock_move_current_state in todo_move_states:
                    if old_product_id != 'product_unchanged':
                        if old_product_id.exists():
                            old_product_id.prepare_and_send_reservation_post_request()

                if ((stock_move_old_state not in todo_move_states and stock_move_current_state and
                     stock_move_current_state in todo_move_states) or \
                    (stock_move_old_state in todo_move_states and stock_move_current_state and
                     stock_move_current_state not in todo_move_states) or \
                    (old_product_qty == 'qty_changed' and (
                            stock_move_current_state in todo_move_states or stock_move_old_state
                            in todo_move_states))) and \
                        (stock_move_current_state not in ['done']):

                    for line in self:
                        line.prepare_and_send_reservation_post_request()


    def prepare_and_send_reservation_post_request(self):
        data = {'product_id': self.id, 'sku': self.default_code,
                'stock_qty': self.virtual_available,
                'price': self.list_price}
        print("Data from product.product %s" % data)
        _logger.info("Loading data to webservice on automated action %s" % data)
        headers = {'Content-Type': 'application/json'}
        data_json = json.dumps({'params': data})
        try:
            requests.post(url=self.env.user.company_id.shopify_post_url, data=data_json,
                          headers=headers)
        except Exception as e:
            _logger.error("Failed to send post request to shopify webservice, reason : %s" % e)
