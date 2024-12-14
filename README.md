# Mathnet
Website Developed for Web Application Development

Overview
This web application is a learning platform that allows teachers to create courses and lessons, and students to enroll in courses, complete lessons, answer questions, and track their progress. Teachers can grade student answers and view student performance within each course.

Features
User Authentication: Secure sign-up and login functionality using Flask-Login.
Course Management:
Teachers can create courses with unique codes.
Courses can be public or private.
Lesson Management:
Teachers can add, edit, and delete lessons.
Lessons can include content, embedded videos, and Desmos graphs, and LaTeX markup langauge.
Question and Answer System:
Teachers can add questions to lessons.
Students can submit answers to questions.
Teachers can grade answers and provide feedback.
Progress Tracking:
Students can mark lessons as completed.
Indicators show which lessons have been completed.
Grade Viewing:
Students can view their grades within each course.
Teachers can view grades for all students in their courses.

Technology Stack
Backend: Python, Flask, SQLAlchemy
Frontend: HTML, CSS (Bootstrap), JavaScript
Database: SQLite (development), can be configured for PostgreSQL or MySQL for production
