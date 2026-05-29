from odoo import models, fields, api

class HrRecruitmentCriteria(models.Model):
    _name = 'hr.recruitment.criteria'
    _description = 'AI Recruitment Criteria'
    _order = 'id desc'

    name = fields.Char(string='Criteria Name', required=True, placeholder="e.g., Senior Python Developer Standard")
    job_id = fields.Many2one('hr.job', string='Job Position', required=True)
    benchmark_score = fields.Integer(string='Benchmark Score', default=70, help="Minimum score to be considered High Potential")
    keyword_required = fields.Text(string='Required Keywords', placeholder="Python, Odoo, PostgreSQL, Docker (Comma separated)")
    
    # Weights configuration
    skills_weight = fields.Float(string='Skills Weight (%)', default=40.0)
    experience_weight = fields.Float(string='Experience Weight (%)', default=40.0)
    education_weight = fields.Float(string='Education Weight (%)', default=20.0)
    min_experience_years = fields.Integer(string='Min Experience Years', default=2)
    is_active = fields.Boolean(string='Active', default=True)
    
    # Smart button count
    applicant_count = fields.Integer(compute='_compute_applicant_count', string='Applicants')

    def _compute_applicant_count(self):
        for rec in self:
            rec.applicant_count = self.env['hr.applicant'].search_count([('job_id', '=', rec.job_id.id)])

    def action_view_applicants(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Applicants Linked to Criteria',
            'res_model': 'hr.applicant',
            'view_mode': 'tree,form',
            'domain': [('job_id', '=', self.job_id.id)],
        }