from odoo import http
from odoo.http import request

class TopCVWebhook(http.Controller):

    @http.route(
        '/topcv/webhook/applicant',
        type='json',
        auth='public',
        methods=['POST'],
        csrf=False
    )

    def receive_cv(self, **post):

        data = request.jsonrequest

        request.env[
            'hr.applicant'
        ].sudo().create_from_topcv(data)

        return {
            'status': 'success'
        }