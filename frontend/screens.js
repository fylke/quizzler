const screenControllers = {};

function registerScreenController(screenName, controller) {
    screenControllers[screenName] = controller;
}

function getScreenController(screenName) {
    return screenControllers[screenName];
}

function showRegisteredScreen(screenName, ...args) {
    const controller = getScreenController(screenName);
    if (!controller || typeof controller.show !== 'function') {
        throw new Error(`Unknown screen controller: ${screenName}`);
    }
    return controller.show(...args);
}

const authScreenController = {
    show(mode = 'login') {
        suppressNextAutoStatusScreen = true;
        clearAuthError();
        toggleAuthMode(mode);
        showScreen('welcomeScreen');
    }
};

const mainScreenController = {
    async show() {
        showScreen('statusScreen');
        updateGuestUpgradeVisibility();
        updateMainCornerIconVisibility();
        await loadQuizTypeButtons();
    }
};

const statsScreenController = {
    async show() {
        showScreen('statsScreen');
        updateGuestUpgradeVisibility();
        document.getElementById('statsCumulativeScore').textContent = '0';
        document.getElementById('statsCompleted').textContent = '0';
        document.getElementById('statsAverageScore').textContent = '0';

        try {
            const response = await fetch(`${API_BASE}/api/stats`);
            if (response.ok) {
                const stats = await response.json();
                document.getElementById('statsCumulativeScore').textContent = stats.cumulativeScore;
                document.getElementById('statsCompleted').textContent = stats.quizzesCompleted;
                document.getElementById('statsAverageScore').textContent = stats.averageScore;
            } else {
                showNotification('Failed to load statistics.');
            }
        } catch (error) {
            console.error('Error loading stats:', error);
            showNotification('Cannot connect to server.');
        }
    }
};

const quizScreenController = {
    show() {
        showScreen('quizScreen');
    },
    async startRandomQuiz() {
        this.show();
        await loadQuestion();
    },
    showSpecificQuiz(data) {
        this.show();
        displayQuiz(data);
    }
};

const resultsScreenController = {
    show(isCorrect, points, correctAnswer, resultImages = [], options = {}) {
        showScreen('resultsScreen');

        const resultsStatus = document.getElementById('resultsStatus');
        const resultsDetails = document.getElementById('resultsDetails');

        if (isCorrect) {
            resultsStatus.textContent = '✓ Correct!';
            resultsStatus.className = 'results-status correct';
            resultsDetails.innerHTML = `
                <p>The destination was: <span class="correct-answer">${correctAnswer}</span></p>
                <p class="points-earned">${points} Points!</p>
            `;
        } else {
            resultsStatus.textContent = '✗ Incorrect';
            resultsStatus.className = 'results-status incorrect';
            resultsDetails.innerHTML = `
                <p>The destination was: <span class="correct-answer">${correctAnswer}</span></p>
                <p class="points-earned">0 Points</p>
            `;
        }

        const resultsScreenEl = document.getElementById('resultsScreen');
        const hintImagesForResults = getAllUnlockedHintImagesForResults();
        resultsScreenEl.dataset.lastScore = points;
        resultsScreenEl.dataset.resultImages = JSON.stringify(resultImages);
        resultsScreenEl.dataset.hintImagesForResults = JSON.stringify(hintImagesForResults);
        resultsScreenEl.dataset.resultCountry = String(correctAnswer || '');
        resultsScreenEl.dataset.scorePreserved = options.scorePreserved ? 'true' : 'false';
        if (Number.isFinite(options.preservedScore)) {
            resultsScreenEl.dataset.preservedScore = String(options.preservedScore);
        } else {
            delete resultsScreenEl.dataset.preservedScore;
        }

        const resultsImagesHeading = document.getElementById('resultsImagesHeading');
        const resultsImagesContainer = document.getElementById('resultsImages');
        if (resultsImagesHeading) {
            if (Array.isArray(resultImages) && resultImages.length > 0) {
                resultsImagesHeading.textContent = `Here are all the pictures from ${correctAnswer}, as well as some bonus pictures`;
                resultsImagesHeading.classList.remove('hidden');
            } else {
                resultsImagesHeading.textContent = '';
                resultsImagesHeading.classList.add('hidden');
            }
        }
        renderImageGallery(resultsImagesContainer, resultImages, 'hint');
    }
};

registerScreenController('auth', authScreenController);
registerScreenController('main', mainScreenController);
registerScreenController('stats', statsScreenController);
registerScreenController('quiz', quizScreenController);
registerScreenController('results', resultsScreenController);