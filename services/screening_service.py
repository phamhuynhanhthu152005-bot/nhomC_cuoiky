def auto_screening(self, data):

    score = 0

    skills = data.get('skills', [])

    required = self.job_id.required_skills.split(',')

    matched = len(
        set(skills) & set(required)
    )

    score += matched * 10

    experience = data.get(
        'experience',
        0
    )

    if experience >= self.job_id.min_experience:
        score += 50

    self.screening_score = score

    if score >= 70:

        self.screening_status = 'qualified'

    else:

        self.screening_status = 'rejected'