from odoo import models, fields

class SkillMaster(models.Model):
    _name = 'skill.master'
    _description = 'Job Search'

    name = fields.Char(string="Employee")

    job_position = fields.Selection([
        ('Business Analyst','Business Analyst'),
        ('Data Analyst','Data Analyst'),
        ('Project Management','Project Management')
    ], string="Job Position")