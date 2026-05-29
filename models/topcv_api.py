import requests

from odoo import models

class TopCVApi(models.AbstractModel):

    _name = 'topcv.api'

    def post_job(self, payload):

        api_url = "https://api.topcv.vn/jobs"

        headers = {
            "Authorization": "Bearer TOKEN",
            "Content-Type": "application/json"
        }

        response = requests.post(
            api_url,
            json=payload,
            headers=headers
        )

        return response.json()