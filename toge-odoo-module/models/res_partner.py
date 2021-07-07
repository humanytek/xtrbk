from odoo import models, fields

class ResPartnerInheritShopifyOdooInventorySalesSynchronisation(models.Model):
    _inherit = 'res.partner'

    shopify_client_id = fields.Char(string="Shopify Id")

