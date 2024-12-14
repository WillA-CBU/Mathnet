function deleteCourse(courseId) {
    fetch('/delete-course', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ courseId: courseId }),
    }).then((_res) => {
        window.location.href = '/home';
    });
}