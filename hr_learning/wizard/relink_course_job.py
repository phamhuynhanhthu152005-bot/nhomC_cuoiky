# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError


class RelinkCourseJob(models.TransientModel):
    """
    Wizard: Re-link Courses → đúng hr.job record

    Vấn đề giải quyết:
    -------------------
    Khi data.xml tạo hr.job records riêng, learning.course.job_position_id
    trỏ tới record đó (VD: id=10). Nhưng hr.employee.job_id trỏ tới record
    khác cùng tên (VD: id=1) được tạo từ HR module.

    Wizard này:
    1. Scan tất cả learning.course
    2. Với mỗi course, tìm hr.job record mà EMPLOYEE đang dùng (theo tên)
    3. Cập nhật course.job_position_id về đúng record đó
    4. Không xóa hr.job cũ – chỉ re-point course

    Sau khi chạy wizard này, domain '=' sẽ hoạt động đúng.
    """
    _name = 'relink.course.job.wizard'
    _description = 'Re-link Courses to correct hr.job records'

    info = fields.Text(
        string='Preview',
        readonly=True,
        default='Nhấn "Phân tích" để xem danh sách courses sẽ được cập nhật.',
    )
    line_ids = fields.One2many(
        comodel_name='relink.course.job.line',
        inverse_name='wizard_id',
        string='Courses to Re-link',
    )
    has_issues = fields.Boolean(compute='_compute_has_issues')

    @api.depends('line_ids')
    def _compute_has_issues(self):
        for rec in self:
            rec.has_issues = bool(rec.line_ids)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_analyze(self):
        """Phân tích và hiển thị các courses có job_position_id sai."""
        self.ensure_one()
        self.line_ids.unlink()

        lines = []
        courses = self.env['learning.course'].search([
            ('job_position_id', '!=', False),
        ])

        # Tìm tất cả hr.job được employee dùng (có ít nhất 1 employee)
        # Đây là các "canonical" records – records mà HR module dùng
        HrJob = self.env['hr.job']
        Employee = self.env['hr.employee']

        for course in courses:
            current_job = course.job_position_id
            job_name = current_job.name.strip()

            # Tìm hr.job records cùng tên mà có employee đang dùng
            employee_job_ids = Employee.search([
                ('job_id.name', '=ilike', job_name),
            ]).mapped('job_id')

            if not employee_job_ids:
                # Không có employee nào dùng job này → không cần re-link
                continue

            # Chọn hr.job được nhiều employee dùng nhất (canonical record)
            canonical_job = employee_job_ids.sorted(
                key=lambda j: Employee.search_count([('job_id', '=', j.id)]),
                reverse=True
            )[0]

            if canonical_job.id != current_job.id:
                # Có mismatch → cần re-link
                lines.append({
                    'wizard_id': self.id,
                    'course_id': course.id,
                    'current_job_id': current_job.id,
                    'target_job_id': canonical_job.id,
                    'employee_count': Employee.search_count([
                        ('job_id', '=', canonical_job.id)
                    ]),
                })

        if lines:
            self.env['relink.course.job.line'].create(lines)
            self.info = (
                'Tìm thấy %d courses cần cập nhật Job Position.\n'
                'Xem chi tiết bên dưới. Nhấn "Áp dụng" để sửa.'
            ) % len(lines)
        else:
            self.info = (
                '✅ Tất cả courses đã trỏ đúng hr.job record.\n'
                'Không cần thực hiện re-link.\n\n'
                'Nếu vẫn thấy danh sách trống, nguyên nhân có thể là:\n'
                '• Courses chưa được gán Job Position.\n'
                '• Employee chưa có Job Position.\n'
                '• Tên Job Position không khớp (kiểm tra khoảng trắng thừa).'
            )

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_apply(self):
        """Thực hiện re-link tất cả courses trong danh sách."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError('Không có courses nào cần cập nhật. Hãy chạy Phân tích trước.')

        updated = 0
        for line in self.line_ids:
            line.course_id.write({
                'job_position_id': line.target_job_id.id,
            })
            updated += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Re-link hoàn tất',
                'message': 'Đã cập nhật %d courses về đúng Job Position.' % updated,
                'type': 'success',
                'sticky': False,
            },
        }


class RelinkCourseJobLine(models.TransientModel):
    """Dòng chi tiết trong wizard Re-link."""
    _name = 'relink.course.job.line'
    _description = 'Re-link Course Job Line'

    wizard_id = fields.Many2one(
        comodel_name='relink.course.job.wizard',
        ondelete='cascade',
    )
    course_id = fields.Many2one(
        comodel_name='learning.course',
        string='Course',
        readonly=True,
    )
    current_job_id = fields.Many2one(
        comodel_name='hr.job',
        string='Current Job (sai)',
        readonly=True,
    )
    target_job_id = fields.Many2one(
        comodel_name='hr.job',
        string='Correct Job (đúng)',
        readonly=True,
    )
    employee_count = fields.Integer(
        string='Employees using correct Job',
        readonly=True,
    )
