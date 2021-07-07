from odoo import models, fields


class ResCompanyInheritShopifyOdooInventorySalesSynchronisation(models.Model):
    _inherit = 'res.company'

    shopify_post_url = fields.Char(string="Shopify webservice post url")

class ResCompany(models.Model):
    _inherit = 'res.company'

    shopify_product_upload_url = fields.Char(string="Shopify product upload url")