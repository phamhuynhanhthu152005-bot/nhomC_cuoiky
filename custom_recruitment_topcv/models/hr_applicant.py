from odoo import models, fields

class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    source_platform = fields.Selection([
        ('topcv', 'TopCV')
    ])

    screening_status = fields.Selection([
        ('pending', 'Pending'),
        ('qualified', 'Qualified'),
        ('rejected', 'Rejected')
    ], default='pending')

    screening_score = fields.Float()
def create_from_topcv(self, data):

    job = self.env['hr.job'].search([
        ('topcv_job_id', '=', data.get('job_id'))
    ], limit=1)

    applicant = self.create({
        'name': data.get('name'),
        'email_from': data.get('email'),
        'partner_phone': data.get('phone'),
        'job_id': job.id,
        'source_platform': 'topcv',
    })

    applicant.auto_screening(data)