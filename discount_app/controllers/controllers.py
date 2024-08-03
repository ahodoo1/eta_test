# -*- coding: utf-8 -*-
# from odoo import http


# class DiscountApp(http.Controller):
#     @http.route('/discount_app/discount_app/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/discount_app/discount_app/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('discount_app.listing', {
#             'root': '/discount_app/discount_app',
#             'objects': http.request.env['discount_app.discount_app'].search([]),
#         })

#     @http.route('/discount_app/discount_app/objects/<model("discount_app.discount_app"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('discount_app.object', {
#             'object': obj
#         })
