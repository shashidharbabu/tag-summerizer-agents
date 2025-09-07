// Closure to track submission count
const submissionCounter = (() => {
    let count = 0;
    return () => {
        count++;
        return count;
    };
})();

const validateBlogForm = (event) => {
    const blogContent = document.getElementById('blogContent').value;
    const termsChecked = document.getElementById('terms').checked;

    if (blogContent.length <= 25) {
        alert('Blog content should be more than 25 characters');
        event.preventDefault();
        return false;
    }
    if (!termsChecked) {
        alert('You must agree to the terms and conditions');
        event.preventDefault();
        return false;
    }

    const blogTitle = document.getElementById('blogTitle').value;
    const authorName = document.getElementById('authorName').value;
    const email = document.getElementById('email').value;
    const category = document.getElementById('category').value;

    const formData = {
        blogTitle,
        authorName,
        email,
        blogContent,
        category,
        termsChecked
    };

    const jsonString = JSON.stringify(formData);
    console.log(jsonString);

    const { blogTitle: title, email: emailAddress } = formData;
    console.log('Title:', title);
    console.log('Email:', emailAddress);

    const submissionDate = new Date().toISOString();
    const updatedFormData = { ...formData, submissionDate };
    console.log('Updated object:', updatedFormData);

    const count = submissionCounter();
    console.log(`Form has been submitted ${count} times.`);

    return true;
};

document.addEventListener('DOMContentLoaded', () => {
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', (event) => {
            const valid = validateBlogForm(event);
            event.preventDefault();
        });
    }
});
