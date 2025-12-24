/**
 * Theme Toggle Script
 * Handles dark/light theme switching with localStorage persistence
 */

document.addEventListener('DOMContentLoaded', function() {
    const themeToggle = document.getElementById('themeToggle');
    const themeIcon = document.getElementById('themeIcon');
    const html = document.documentElement;

    /**
     * Update the theme icon based on current theme
     * @param {string} theme - 'dark' or 'light'
     */
    function updateThemeIcon(theme) {
        if (theme === 'dark') {
            themeIcon.className = 'fa-solid fa-sun';
        } else {
            themeIcon.className = 'fa-solid fa-moon';
        }
    }

    // Set initial icon based on current theme
    const currentTheme = localStorage.getItem('theme') || 'dark';
    updateThemeIcon(currentTheme);

    // Toggle theme on button click
    themeToggle.addEventListener('click', function(e) {
        e.preventDefault();
        const currentTheme = html.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

        html.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        updateThemeIcon(newTheme);
    });
});
