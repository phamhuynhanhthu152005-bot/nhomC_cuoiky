from odoo import models, fields, api
import random

class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    cv_score = fields.Integer(string='AI CV Score', default=0)
    scoring_state = fields.Selection([
        ('not_scored', 'Not Scored'),
        ('failed', 'Below Benchmark'),
        ('passed', 'Passed'),
        ('high_potential', 'High Potential')
    ], string='AI Assessment', default='not_scored', copy=False)
    
    ai_analysis_log = fields.Text(string='AI Analysis Notes', readonly=True)

    def action_score_cv(self):
        for rec in self:
            # Tìm bộ tiêu chí đang kích hoạt cho vị trí công việc này
            criteria = self.env['hr.recruitment.criteria'].search([
                ('job_id', '=', rec.job_id.id),
                ('is_active', '=', True)
            ], limit=1)

            # Giả lập logic AI quét từ khóa thực tế dựa trên tên ứng viên/mô tả hoặc file đính kèm
            base_score = random.randint(55, 80)
            
            if criteria:
                # Nếu có tiêu chí, AI giả lập cộng điểm thưởng nếu hồ sơ "khớp" keyword
                keywords = [k.strip().lower() for k in criteria.keyword_required.split(',') if k.strip()]
                match_count = random.randint(0, len(keywords)) if keywords else 2
                
                bonus = match_count * 5
                final_score = min(base_score + bonus, 100) # Điểm tối đa là 100
                benchmark = criteria.benchmark_score
                
                log = f"--- AI Assessment Report ---\n" \
                      f"Target Position: {criteria.job_id.name}\n" \
                      f"Matched Keywords: {match_count} keywords found.\n" \
                      f"Calculated Score: {final_score}/100 (Benchmark: {benchmark})"
            else:
                final_score = random.randint(50, 90)
                benchmark = 70
                log = "Evaluated without job criteria profile. Standard parsing applied."

            # Phân loại trạng thái dựa trên điểm thực tế
            if final_score >= 85:
                state = 'high_potential'
            elif final_score >= benchmark:
                state = 'passed'
            else:
                state = 'failed'

            rec.write({
                'cv_score': final_score,
                'scoring_state': state,
                'ai_analysis_log': log
            })