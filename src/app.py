from flask import Flask, jsonify, request
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import pyodbc

app = Flask(__name__)

# Kết nối đến CSDL SQL Server
conn = pyodbc.connect('DRIVER={SQL Server};'
                      'SERVER=DESKTOP-RE1ARQC\MSSQLSERVER01;'
                      'DATABASE=ITJobsDB;'
                      'Trusted_Connection=yes;')

# Tạo một đối tượng cursor để thực hiện truy vấn
cursor = conn.cursor()

# Thực hiện truy vấn để lấy dữ liệu từ bảng JobPosts và kết nối với Skills thông qua RequirementSkills,
# cũng như kết nối với Districts và Provinces để lấy thông tin về DistrictName và ProvinceName
cursor.execute('''
    SELECT 
        jp.Id as JobPostId, jp.Title, jp.EmployerId, jp.YearsOfExperience, jp.Salary, jp.EmploymentType, jp.ExpiredDate,
        rs.SkillId, s.SkillName AS SkillName,
        p.ProvinceName, d.DistrictName,
		c.Id as CompanyId, c.CompanyName, c.LogoUrl
    FROM JobPosts jp
    INNER JOIN RequirementSkills rs ON jp.Id = rs.JobPostId
    INNER JOIN Skills s ON rs.SkillId = s.Id
    INNER JOIN Districts d ON jp.DistrictId = d.Id
    INNER JOIN Provinces p ON jp.ProvinceId = p.Id
    INNER JOIN Employers e ON jp.EmployerId = e.Id
    INNER JOIN Companies c ON e.CompanyId = c.Id
''')

job_data = cursor.fetchall()

job_listings = []

job_skills_dict = {}

for row in job_data:
    job_id = row.JobPostId

    if job_id not in job_skills_dict:
        job_skills_dict[job_id] = {
            'JobPostId': job_id,
            'Title': row.Title,
            'EmployerId': row.EmployerId,
            'YearsOfExperience': row.YearsOfExperience,
            'Salary': row.Salary,
            'EmploymentType': row.EmploymentType,
            'ExpiredDate': row.ExpiredDate,
            'ProvinceName': row.ProvinceName,
            'DistrictName': row.DistrictName,
            'SkillsRequired': [row.SkillName],
            'CompanyName': row.CompanyName,
            'CompanyId': row.CompanyId,
            'LogoUrl': row.LogoUrl,
        }
    else:
        # Nếu công việc đã tồn tại, thêm kỹ năng vào danh sách kỹ năng của công việc
        job_skills_dict[job_id]['SkillsRequired'].append(row.SkillName)


job_listings = list(job_skills_dict.values())

conn.close()

def build_similarity_matrix(jobs):
    skills_matrix = np.zeros((len(jobs), len(set(skill for job in jobs for skill in job['SkillsRequired']))))

    # Tạo ma trận mô tả kỹ năng cho mỗi công việc
    for i, job in enumerate(jobs):
        for skill in job['SkillsRequired']:
            skills_matrix[i, list(set(skill for job in jobs for skill in job['SkillsRequired'])).index(skill)] = 1

    # Tính toán ma trận tương đồng cosine
    similarity_matrix = cosine_similarity(skills_matrix, skills_matrix)

    return similarity_matrix

similarity_matrix = build_similarity_matrix(job_listings)

@app.route('/recommend', methods=['POST'])
def recommend_jobs():
    data = request.get_json()

    # Assuming the data includes information from the user's resume
    user_resume = data.get('resume', {})

    # Get job recommendations using Item-based Collaborative Filtering
    recommendations = get_recommendations(user_resume)

    return jsonify({'recommendations': recommendations})

def get_recommendations(user_resume):
    # Dummy recommendation logic
    # Find jobs similar to the ones in the user's resume
    user_skills = set(user_resume.get('skills', []))
    user_skills_vector = np.zeros((1, similarity_matrix.shape[1]))
    for skill in user_skills:
        if skill in set(skill for job in job_listings for skill in job['SkillsRequired']):
            index = list(set(skill for job in job_listings for skill in job['SkillsRequired'])).index(skill)
            if index < len(user_skills_vector[0]):
                user_skills_vector[0, index] = 1

    # Tính toán tương đồng giữa user và jobs
    user_job_similarity = cosine_similarity(user_skills_vector, similarity_matrix)[0]

    # Lấy danh sách công việc dựa trên tương đồng và sắp xếp giảm dần theo độ tương đồng
    ranked_jobs_indices = np.argsort(user_job_similarity)[::-1]
    recommended_jobs = [job_listings[i] for i in ranked_jobs_indices]

    return recommended_jobs

if __name__ == '__main__':
    app.run(debug=True)
