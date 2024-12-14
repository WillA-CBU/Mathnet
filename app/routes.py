from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for
from flask_login import login_required, current_user
from .models import Course, User, Lesson, Question, Answer, LessonCompletion
from . import db
import json, string, random, re, bleach
from datetime import datetime


routes = Blueprint('routes', __name__)

# Define additional allowed tags
ADDITIONAL_ALLOWED_TAGS = [
    'math', 'mi', 'mo', 'mn', 'msup', 'msub', 'mfrac',
    'msqrt', 'mroot', 'mtable', 'mtr', 'mtd', 'mstyle',
    'mrow', 'annotation', 'semantics', 'iframe', 'div', 'span'
]

# Define additional allowed attributes
ADDITIONAL_ALLOWED_ATTRIBUTES = {
    'iframe': ['src', 'width', 'height', 'frameborder', 'allowfullscreen', 'allow'],
    'div': ['class', 'id', 'data-desmos-state'],
    'span': ['class']
}

# Combine with default allowed tags and attributes
ALLOWED_TAGS = list(bleach.sanitizer.ALLOWED_TAGS) + ADDITIONAL_ALLOWED_TAGS
ALLOWED_ATTRIBUTES = bleach.sanitizer.ALLOWED_ATTRIBUTES.copy()
for tag, attrs in ADDITIONAL_ALLOWED_ATTRIBUTES.items():
    ALLOWED_ATTRIBUTES.setdefault(tag, []).extend(attrs)

ALLOWED_PROTOCOLS = list(bleach.sanitizer.ALLOWED_PROTOCOLS) + ['https']

def sanitize_content(content):
    return bleach.clean(
        content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True
    )

def generate_course_code(length=6):
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def convert_youtube_url(url):
    """
    Converts a standard YouTube watch URL to an embed URL.
    If the URL is already an embed URL, it returns it unchanged.
    """
    watch_pattern = r'(https?://)?(www\.)?youtube\.com/watch\?v=([A-Za-z0-9_-]{11})'
    embed_pattern = r'(https?://)?(www\.)?youtube\.com/embed/([A-Za-z0-9_-]{11})'
    
    watch_match = re.match(watch_pattern, url)
    if watch_match:
        video_id = watch_match.group(3)
        return f"https://www.youtube.com/embed/{video_id}"
    
    embed_match = re.match(embed_pattern, url)
    if embed_match:
        # URL is already in embed format
        return url
    
    # If the URL doesn't match expected patterns, return None or handle accordingly
    return None

@routes.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('routes.home'))
    else:
        return redirect(url_for('auth.sign_up'))

@routes.route('/home')
@login_required
def home():
    # Courses the user has created
    created_courses = current_user.created_courses

    # Courses the user has joined but did not create
    joined_courses = [course for course in current_user.courses if course.creator != current_user]

    return render_template(
        'home.html',
        user=current_user,
        created_courses=created_courses,
        joined_courses=joined_courses
    )

@routes.route('/delete-course', methods=['POST'])
@login_required
def delete_course():
    course_id = request.form.get('course_id')
    course = Course.query.get_or_404(course_id)
    if course.creator != current_user:
        flash('Unauthorized action.', category='error')
        return redirect(url_for('routes.home'))
    db.session.delete(course)
    db.session.commit()
    flash('Course deleted.', category='success')
    return redirect(url_for('routes.home'))

@routes.route('/course/<int:course_id>')
@login_required
def course(course_id):
    course = Course.query.get_or_404(course_id)

    # Check if the user is enrolled or is the creator
    if current_user != course.creator and current_user not in course.students:
        flash('You are not enrolled in this course.', category='error')
        return redirect(url_for('routes.home'))

    # Get all lessons for the course
    lessons = course.lessons

    # Get IDs of lessons the current user has completed
    completed_lessons = db.session.query(LessonCompletion.lesson_id).filter_by(user_id=current_user.id).all()
    completed_lessons_ids = {lesson_id for (lesson_id,) in completed_lessons}

    return render_template(
        'course.html',
        course=course,
        lessons=lessons,
        completed_lessons_ids=completed_lessons_ids,
        user=current_user
    )

@routes.route('/create-course', methods=['GET', 'POST'])
@login_required
def create_course():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')

        if len(title) < 1:
            flash('Course title is too short!', category='error')
        else:
            code = generate_course_code()
            while Course.query.filter_by(code=code).first():
                code = generate_course_code()
            new_course = Course(title=title, description=description, code=code, creator=current_user)
            db.session.add(new_course)
            db.session.commit()
            flash('Course created!', category='success')
            return redirect(url_for('routes.home'))
    return render_template('create_course.html', user=current_user)

@routes.route('/join-course', methods=['GET', 'POST'])
@login_required
def join_course():
    if request.method == 'POST':
        # Check if joining via course ID from search results
        course_id = request.form.get('course_id')
        if course_id:
            course = Course.query.get(course_id)
            if course:
                if course in current_user.courses:
                    flash('You are already enrolled in this course.', category='info')
                else:
                    current_user.courses.append(course)
                    db.session.commit()
                    flash('Joined course!', category='success')
                return redirect(url_for('routes.home'))
            else:
                flash('Course not found.', category='error')
        else:
            # Joining via course code
            code = request.form.get('code')
            course = Course.query.filter_by(code=code).first()
            if course:
                if course in current_user.courses:
                    flash('You are already enrolled in this course.', category='info')
                else:
                    current_user.courses.append(course)
                    db.session.commit()
                    flash('Joined course!', category='success')
                return redirect(url_for('routes.home'))
            else:
                flash('Invalid course code.', category='error')
    courses = None
    if request.args.get('search'):
        search = request.args.get('search')
        courses = Course.query.filter(
            Course.title.contains(search),
            Course.is_private.is_(False)
        ).all()
    return render_template('join_course.html', user=current_user, courses=courses)

@routes.route('/course/<int:course_id>/remove-student', methods=['POST'])
@login_required
def remove_student(course_id):
    course = Course.query.get_or_404(course_id)
    if current_user != course.creator:
        flash('You do not have permission to perform this action.', category='error')
        return redirect(url_for('routes.course', course_id=course_id))

    student_id = request.form.get('student_id')
    student = User.query.get(student_id)
    if student in course.students:
        course.students.remove(student)
        db.session.commit()
        flash(f'Removed {student.firstName} from the course.', category='success')
    else:
        flash('Student not found in this course.', category='error')
    return redirect(url_for('routes.course', course_id=course_id))

@routes.route('/course/<int:course_id>/toggle-privacy', methods=['POST'])
@login_required
def toggle_course_privacy(course_id):
    course = Course.query.get_or_404(course_id)
    if current_user != course.creator:
        flash('You do not have permission to perform this action.', category='error')
        return redirect(url_for('routes.course', course_id=course_id))

    course.is_private = not course.is_private
    db.session.commit()
    status = 'private' if course.is_private else 'public'
    flash(f'Course is now {status}.', category='success')
    return redirect(url_for('routes.course', course_id=course_id))

@routes.route('/course/<int:course_id>/add-lesson', methods=['GET', 'POST'])
@login_required
def add_lesson(course_id):
    course = Course.query.get_or_404(course_id)
    if current_user != course.creator:
        flash('You do not have permission to add lessons.', 'error')
        return redirect(url_for('routes.course', course_id=course_id))
    if request.method == 'POST':
        title = request.form['title']
        video_url_input = request.form['video_url']
        content_input = request.form['content']
        desmos_state = request.form.get('desmos_state')
        
        # Convert the video URL to embed format
        video_url = convert_youtube_url(video_url_input)
        if not video_url:
            flash('Invalid YouTube URL. Please provide a valid URL.', 'danger')
            return render_template('add_lesson.html', course=course, user=current_user)
        
        sanitized_content = sanitize_content(content_input)
        lesson = Lesson(
            course_id=course.id,
            title=title,
            video_url=video_url,
            content=sanitized_content,
            desmos_state=desmos_state,
        
        )
        db.session.add(lesson)
        db.session.commit()
        flash('Lesson added successfully.', 'success')
        return redirect(url_for('routes.course', course_id=course.id))
    return render_template('add_lesson.html', course=course, user=current_user)

@routes.route('/lesson/<int:lesson_id>', methods=['GET', 'POST'])
@login_required
def view_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    course = lesson.course

    # Check if the user is enrolled or is the creator
    if current_user not in course.students and current_user != course.creator:
        flash('You are not enrolled in this course.', category='error')
        return redirect(url_for('routes.home'))

    # Determine if the lesson is completed by the current user
    completion = LessonCompletion.query.filter_by(lesson_id=lesson.id, user_id=current_user.id).first()
    completed = completion is not None

    if request.method == 'POST':
        if not completed:
            # Mark the lesson as completed
            new_completion = LessonCompletion(lesson_id=lesson.id, user_id=current_user.id)
            db.session.add(new_completion)
            db.session.commit()
            flash('Lesson marked as completed.', category='success')
            completion = True
            return redirect(url_for('routes.view_lesson', lesson_id=lesson.id))

    questions = lesson.questions
    return render_template('lesson.html', lesson=lesson, course=course, questions=questions, completed=completed, user=current_user)

@routes.route('/lesson/<int:lesson_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    course = lesson.course

    if current_user != course.creator:
        flash('You do not have permission to edit this lesson.', 'error')
        return redirect(url_for('routes.view_lesson', lesson_id=lesson.id))

    if request.method == 'POST':
        lesson.title = request.form['title']
        video_url_input = request.form['video_url']
        lesson.content = request.form['content']
        
        # Convert the video URL to embed format
        video_url = convert_youtube_url(video_url_input)
        if not video_url:
            flash('Invalid YouTube URL. Please provide a valid URL.', 'danger')
            return render_template('edit_lesson.html', lesson=lesson, user=current_user)
        
        lesson.video_url = video_url
        lesson.content = sanitize_content(request.form['content'])
        db.session.commit()
        flash('Lesson updated successfully.', 'success')
        return redirect(url_for('routes.view_lesson', lesson_id=lesson.id))

    return render_template('edit_lesson.html', lesson=lesson, user=current_user)

@routes.route('/courses/<int:course_id>/lessons/<int:lesson_id>/add_question', methods=['GET', 'POST'])
@login_required
def add_question(course_id, lesson_id):
    course = Course.query.get_or_404(course_id)
    lesson = Lesson.query.get_or_404(lesson_id)
    if course.creator_id != current_user.id:
        flash('Only the course creator can add questions.', 'danger')
        return redirect(url_for('routes.view_lesson', course_id=course_id, lesson_id=lesson_id))
    if request.method == 'POST':
        prompt = request.form['prompt']
        question = Question(prompt=prompt, lesson=lesson)
        db.session.add(question)
        db.session.commit()
        flash('Question added successfully.', 'success')
        return redirect(url_for('routes.view_lesson', course_id=course_id, lesson_id=lesson_id))
    return render_template('add_question.html', course=course, lesson=lesson, user=current_user)

@routes.route('/courses/<int:course_id>/lessons/<int:lesson_id>/questions/<int:question_id>/answer', methods=['GET', 'POST'])
@login_required
def answer_question(course_id, lesson_id, question_id):
    course = Course.query.get_or_404(course_id)
    lesson = Lesson.query.get_or_404(lesson_id)
    question = Question.query.get_or_404(question_id)
    if not course.students.filter_by(id=current_user.id).first():
        flash('You must be enrolled in the course to answer questions.', 'danger')
        return redirect(url_for('routes.view_lesson', course_id=course_id, lesson_id=lesson_id))
    existing_answer = Answer.query.filter_by(student_id=current_user.id, question_id=question_id).first()
    if request.method == 'POST':
        content = request.form['content']
        if existing_answer:
            existing_answer.content = content
            existing_answer.submitted_at = datetime.utcnow()
        else:
            answer = Answer(content=content, student=current_user, question=question)
            db.session.add(answer)
        db.session.commit()
        flash('Your answer has been submitted.', 'success')
        return redirect(url_for('routes.view_lesson', course_id=course_id, lesson_id=lesson_id))
    return render_template('answer_question.html', question=question, existing_answer=existing_answer, user=current_user)

@routes.route('/courses/<int:course_id>/lessons/<int:lesson_id>/grade_answers', methods=['GET'])
@login_required
def grade_answers(course_id, lesson_id):
    course = Course.query.get_or_404(course_id)
    lesson = Lesson.query.get_or_404(lesson_id)
    if course.creator_id != current_user.id:
        flash('Only the course creator can grade answers.', 'danger')
        return redirect(url_for('routes.view_lesson', course_id=course_id, lesson_id=lesson_id))
    # Get all answers for the lesson's questions
    answers = Answer.query.join(Question).filter(Question.lesson_id == lesson_id).all()
    return render_template('grade_answers.html', course=course, lesson=lesson, answers=answers, user=current_user)

@routes.route('/answers/<int:answer_id>/grade', methods=['GET', 'POST'])
@login_required
def grade_answer(answer_id):
    answer = Answer.query.get_or_404(answer_id)
    question = answer.question
    lesson = question.lesson
    course = lesson.course
    if course.creator_id != current_user.id:
        flash('Only the course creator can grade answers.', 'danger')
        return redirect(url_for('routes.grade_answers', course_id=course.id, lesson_id=lesson.id))
    if request.method == 'POST':
        grade = request.form['grade']
        feedback = request.form.get('feedback', '')
        answer.grade = float(grade)
        answer.feedback = feedback
        db.session.commit()
        flash('Answer graded successfully.', 'success')
        return redirect(url_for('routes.grade_answers', course_id=course.id, lesson_id=lesson.id))
    return render_template('grade_answer.html', answer=answer, user=current_user)

@routes.route('/my_grades', methods=['GET'])
@login_required
def my_grades():
    # Get all graded answers for the current student
    answers = Answer.query.filter_by(student_id=current_user.id).filter(Answer.grade != None).all()
    return render_template('my_grades.html', answers=answers)

@routes.route('/courses/<int:course_id>/lessons/<int:lesson_id>', methods=['GET'])
@login_required
def lesson(course_id, lesson_id):
    course = Course.query.get_or_404(course_id)
    lesson = Lesson.query.get_or_404(lesson_id)
    questions = lesson.questions
    return render_template('lesson.html', course=course, lesson=lesson, questions=questions, user=current_user)

@routes.route('/course/<int:course_id>/my_grades', methods=['GET'])
@login_required
def my_course_grades(course_id):
    course = Course.query.get_or_404(course_id)

    # Check if the user is enrolled in the course
    if current_user not in course.students and current_user != course.creator:
        flash('You are not enrolled in this course.', 'danger')
        return redirect(url_for('routes.home'))

    # Get all graded answers submitted by the student for this course
    answers = Answer.query.join(Question).join(Lesson).filter(
        Answer.student_id == current_user.id,
        Question.lesson_id == Lesson.id,
        Lesson.course_id == course.id,
        Answer.grade != None
    ).all()

    # Calculate average grade for this course
    if answers:
        total_grade = sum([answer.grade for answer in answers])
        average_grade = total_grade / len(answers)
    else:
        average_grade = None

    return render_template('student_course_grades.html', course=course, answers=answers, average_grade=average_grade, user=current_user)

@routes.route('/course/<int:course_id>/grades', methods=['GET'])
@login_required
def course_grades(course_id):
    course = Course.query.get_or_404(course_id)

    # Check if the current user is the course creator
    if course.creator_id != current_user.id:
        flash('Only the course creator can view this page.', 'danger')
        return redirect(url_for('routes.home'))

    # Get all students enrolled in the course
    students = course.students.all()

    # Collect grades for each student
    student_grades = []

    for student in students:
        # Get all graded answers for the student in this course
        answers = Answer.query.join(Question).join(Lesson).filter(
            Answer.student_id == student.id,
            Question.lesson_id == Lesson.id,
            Lesson.course_id == course.id,
            Answer.grade != None
        ).all()

        if answers:
            total_grade = sum([answer.grade for answer in answers])
            average_grade = total_grade / len(answers)
        else:
            average_grade = None

        student_grades.append({
            'student': student,
            'average_grade': average_grade,
            'answers': answers
        })

    return render_template('teacher_course_grades.html', course=course, student_grades=student_grades, user=current_user)
