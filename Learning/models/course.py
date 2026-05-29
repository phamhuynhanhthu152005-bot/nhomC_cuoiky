from odoo import models, fields

class LearningCourse(models.Model):
    _name='learning.course'
    _description='Learning Course'

    name = fields.Char(
        string='Course Name',
        required=True
    )

    job_position = fields.Selection([
        ('Business Analyst','Business Analyst'),
        ('Data Analyst','Data Analyst'),
        ('Project Management','Project Management')
    ], string='Job Position')

    provider = fields.Char(
        string='Provider'
    )

    duration = fields.Char(
        string='Duration'
    )

    description = fields.Text(
        string='Description'
    )