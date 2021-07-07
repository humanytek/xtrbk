from odoo import models, fields

class SaleOrderInheritShopifyOdooInventorySalesSynchronisation(models.Model):
  _inherit = 'sale.order'

  shopify_sale_order_id = fields.Char(string="Shopify Order ID") 
  metodo_de_pago = fields.Char(string="Metodo de pago")
  metodo_de_envio_shopify = fields.Char(string="Envío")
  shopify_number = fields.Char(string="Orden")
