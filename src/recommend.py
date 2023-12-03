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
            'skills': [row.SkillName],
            'CompanyName': row.CompanyName,
            'CompanyId': row.CompanyId,
            'LogoUrl': row.LogoUrl,
        }
    else:
        # Nếu công việc đã tồn tại, thêm kỹ năng vào danh sách kỹ năng của công việc
        job_skills_dict[job_id]['skills'].append(row.SkillName)


job_listings = list(job_skills_dict.values())

conn.close()

# Tập hợp tất cả các kỹ năng 
skill_set = set([skill for job in job_listings for skill in job["skills"]])

# Hàm xây dựng vector skills cho 1 tin tuyển dụng
def vectorize_skills(job, skill_set):
    v =  [1 if skill in job['skills'] else 0 for skill in skill_set] 
    return v


# Xây dựng ma trận vector skills cho các tin tuyển dụng 
job_skill_matrix = np.zeros((len(job_listings), len(skill_set)))
# print(job_skill_matrix)
for i, job in enumerate(job_listings):
    v = vectorize_skills(job, skill_set)
    job_skill_matrix[i,:] = v

@app.route("/recommend", methods=["POST"])
def recommend():
    user_resume = request.json.get('resume', {})
    user_skills = user_resume.get('skills', [])
    
    # Vector hóa skills cho ứng viên
    candidate_vector = vectorize_skills({"skills": user_skills}, skill_set)
    candidate_vector = np.array(candidate_vector)

    # Tính độ tương đồng vs mỗi job
    similarities = cosine_similarity(candidate_vector.reshape(1,-1), job_skill_matrix)[0]
    
    # Sắp xếp top jobs
    top_jobs = sorted(list(zip(job_listings, similarities)), key=lambda x: x[1], reverse=True) 

    return jsonify([job[0] for job in top_jobs])

if __name__ == "__main__":
   app.run()