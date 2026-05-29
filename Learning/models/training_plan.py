from odoo import models, fields

class TrainingPlan(models.Model):
    _name = 'training.plan'
    _description = 'Training Plan'

    employee = fields.Many2one(
        'hr.employee',
        string='Employee'
    )

    course_id = fields.Many2one(
        'learning.course',
        string='Course'
    )

    start_date = fields.Date()

    end_date = fields.Date()

    status = fields.Selection([
        ('planned','Planned'),
        ('ongoing','Ongoing'),
        ('completed','Completed')
    ], default='planned')