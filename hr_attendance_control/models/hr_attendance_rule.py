from odoo import models, fields, api

class HrAttendanceRule(models.Model):
    """
    Bảng cấu hình rule phát hiện vi phạm.
    HR Manager có thể thêm/sửa rule mà không cần sửa code.
    """
    _name = 'hr.attendance.rule'
    _description = 'Attendance Violation Rule'
    _order = 'violation_type, threshold_minutes'

    name = fields.Char('Tên rule', required=True)
    violation_type = fields.Selection([
        ('late', 'Đi muộn'),
        ('early_leave', 'Về sớm'),
        ('absence', 'Vắng mặt'),
        ('insufficient_hours', 'Thiếu giờ làm'),
    ], string='Loại vi phạm', required=True)

    # Ngưỡng kích hoạt rule
    threshold_minutes = fields.Float(
        'Ngưỡng (phút)',
        help='Số phút tối thiểu để kích hoạt rule này. '
             'VD: 15 = đi muộn hơn 15 phút mới ghi nhận vi phạm.'
    )
    threshold_minutes_max = fields.Float(
        'Ngưỡng tối đa (phút)',
        help='Để trống nếu không có giới hạn trên. '
             'Dùng để phân tầng: 0-15 phút = nhẹ, 15-30 = vừa, >30 = nặng.'
    )

    severity = fields.Selection([
        ('minor', 'Nhẹ'),
        ('moderate', 'Vừa'),
        ('major', 'Nặng'),
    ], string='Mức độ', required=True, default='minor')

    penalty_points = fields.Integer(
        'Điểm vi phạm',
        help='Điểm tích lũy trong tháng. Dùng cho logic escalation.'
    )

    # Cách tính phạt
    penalty_type = fields.Selection([
        ('fixed', 'Cố định (VNĐ)'),
        ('percent_daily', '% lương ngày'),
        ('percent_hourly', '% lương theo giờ thiếu'),
    ], string='Cách tính phạt', default='percent_daily')

    penalty_value = fields.Float(
        'Giá trị phạt',
        help='Nếu Fixed: số tiền VNĐ. Nếu Percent: % (vd 1.5 = 1.5%).'
    )

    # Áp dụng cho ai
    department_ids = fields.Many2many(
        'hr.department', string='Phòng ban áp dụng',
        help='Để trống = áp dụng toàn công ty.'
    )
    job_ids = fields.Many2many(
        'hr.job', string='Chức danh áp dụng',
        help='Để trống = áp dụng mọi chức danh.'
    )

    grace_period_minutes = fields.Integer(
        'Khoảng tha thứ (phút)', default=5,
        help='Số phút buffer: check-in muộn trong khoảng này không bị phạt.'
    )
    requires_explanation = fields.Boolean(
        'Yêu cầu giải trình', default=True
    )
    explanation_deadline_hours = fields.Integer(
        'Deadline giải trình (giờ)', default=48
    )
    is_active = fields.Boolean('Đang kích hoạt', default=True)

    def applies_to_employee(self, employee):
        """Kiểm tra rule này có áp dụng cho nhân viên không"""
        if self.department_ids and employee.department_id not in self.department_ids:
            return False
        if self.job_ids and employee.job_id not in self.job_ids:
            return False
        return True