// Quiz State — only tracks the authenticated user; all quiz progress lives on the backend.
let quizState = {
    user: null,
    currentQuizId: null,
    hintHistory: {},
    hintImagesByDifficulty: {},
    unlockedHintDifficulties: [],
    liveHintDifficulty: null,
    liveRemainingGuesses: null,
    viewedHintDifficulty: null
};

let csrfToken = null;

const API_BASE = window.location.origin;
let authMode = 'login';
let submitting = false; // guards against double-click on submit
let hintCounterAnimationTimeout = null;
let remainingGuessesAnimationTimeout = null;
const COUNTER_PUFF_DURATION_MS = 340;

// Validation rules fetched from the backend — single source of truth.
// Fallback defaults are used until the fetch completes.
let validationRules = {
    password: { minLength: 8, maxLength: 128 },
    destination: {
        nameMaxLength: 128,
        hintCount: 5,
        hintMaxLength: 256,
        imagesMinCount: 2,
        imagesMaxCount: 10,
        answersMinCount: 1,
        answersMaxCount: 20,
        answerMaxLength: 128
    }
};

async function loadValidationRules() {
    try {
        const response = await fetch(`${API_BASE}/api/validation-rules`);
        if (response.ok) {
            validationRules = await response.json();
        }
    } catch (error) {
        console.error('Failed to load validation rules, using defaults:', error);
    }
}

// ==================== UI Utilities ====================

function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(screen => {
        screen.classList.add('hidden');
        screen.classList.remove('screen-fade-in');
    });
    const target = document.getElementById(screenId);
    target.classList.remove('hidden');
    target.classList.add('screen-fade-in');
}

function showNotification(message, type = 'error') {
    // Remove any existing notification
    const existing = document.getElementById('appNotification');
    if (existing) existing.remove();

    const el = document.createElement('div');
    el.id = 'appNotification';
    el.className = `app-notification app-notification-${type}`;
    el.setAttribute('role', 'alert');
    el.textContent = message;
    document.body.appendChild(el);

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        el.classList.add('app-notification-fade');
        el.addEventListener('transitionend', () => el.remove());
    }, 5000);
}

function showAuthError(message) {
    const el = document.getElementById('authError');
    if (el) {
        el.textContent = message;
        el.style.display = 'block';
    }
}

function clearAuthError() {
    const el = document.getElementById('authError');
    if (el) {
        el.textContent = '';
        el.style.display = 'none';
    }
}

// ==================== Auth ====================

async function loadUser() {
    try {
        const response = await fetch(`${API_BASE}/api/me`);
        if (response.status === 401) {
            showScreen('welcomeScreen');
            return;
        }
        if (!response.ok) {
            showNotification('Unable to reach server. Please try again.');
            showScreen('welcomeScreen');
            return;
        }
        const data = await response.json();
        quizState.user = data;
        csrfToken = data.csrfToken || null;
        const restoredActiveQuiz = await restoreActiveQuiz();
        if (!restoredActiveQuiz) {
            showStatusScreen();
        }
    } catch (error) {
        console.error('Error checking auth status:', error);
        showNotification('Cannot connect to server.');
        showScreen('welcomeScreen');
    }
}

async function restoreActiveQuiz() {
    try {
        const response = await fetch(`${API_BASE}/api/quiz/active`);
        if (response.status === 404) {
            return false;
        }
        if (!response.ok) {
            showNotification('Unable to restore active quiz.');
            return false;
        }

        const activeQuiz = await response.json();
        showScreen('quizScreen');
        displayQuiz(activeQuiz);
        return true;
    } catch (error) {
        console.error('Error restoring active quiz:', error);
        return false;
    }
}

function toggleAuthMode(mode) {
    authMode = mode;
    const nameField = document.getElementById('name');
    const authButton = document.getElementById('authButton');
    const switchToRegister = document.getElementById('switchToRegister');
    const switchToLogin = document.getElementById('switchToLogin');
    const authHeading = document.getElementById('authHeading');
    const authSubtext = document.getElementById('authSubtext');

    if (mode === 'register') {
        nameField.classList.remove('hidden');
        authButton.textContent = 'Create Account';
        switchToRegister.classList.add('hidden');
        switchToLogin.classList.remove('hidden');
        authHeading.textContent = 'Create your account';
        authSubtext.textContent = 'Register and start the quiz.';
        updatePasswordStrength();
    } else {
        nameField.classList.add('hidden');
        authButton.textContent = 'Log In';
        switchToRegister.classList.remove('hidden');
        switchToLogin.classList.add('hidden');
        authHeading.textContent = 'Welcome Back';
        authSubtext.textContent = 'Log in to continue.';
        document.getElementById('passwordStrengthContainer').classList.add('hidden');
    }
}

function getPasswordStrength(password) {
    if (!password) return { level: 0, label: '' };
    let score = 0;
    if (password.length >= validationRules.password.minLength) score++;
    if (password.length >= 12) score++;
    if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
    if (/\d/.test(password)) score++;
    if (/[^a-zA-Z0-9]/.test(password)) score++;

    if (password.length < validationRules.password.minLength) return { level: 1, label: 'Too short' };
    if (score <= 2) return { level: 1, label: 'Weak' };
    if (score === 3) return { level: 2, label: 'Fair' };
    if (score === 4) return { level: 3, label: 'Good' };
    return { level: 4, label: 'Strong' };
}

function updatePasswordStrength() {
    const password = document.getElementById('password').value;
    const container = document.getElementById('passwordStrengthContainer');
    const fill = document.getElementById('passwordStrengthFill');
    const label = document.getElementById('passwordStrengthLabel');

    if (!password || authMode !== 'register') {
        container.classList.add('hidden');
        return;
    }

    container.classList.remove('hidden');
    const strength = getPasswordStrength(password);
    const classes = ['strength-weak', 'strength-fair', 'strength-good', 'strength-strong'];
    const strengthClass = classes[strength.level - 1] || '';

    fill.className = 'password-strength-fill ' + strengthClass;
    label.className = 'password-strength-label ' + strengthClass;
    label.textContent = strength.label;
}

async function handleAuth() {
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value.trim();
    const name = document.getElementById('name').value.trim();

    // Mark email as touched so validation styles apply
    document.getElementById('email').classList.add('touched');

    if (!email || !password) {
        showAuthError('Please fill in all required fields.');
        return;
    }

    if (authMode === 'register' && password.length < validationRules.password.minLength) {
        showAuthError(`Password must be at least ${validationRules.password.minLength} characters.`);
        return;
    }

    // Client-side email format check
    const emailInput = document.getElementById('email');
    if (!emailInput.validity.valid) {
        showAuthError('Please enter a valid email address.');
        return;
    }

    clearAuthError();

    const payload = { email, password };
    if (authMode === 'register') {
        payload.name = name;
    }

    try {
        const response = await fetch(`${API_BASE}/api/${authMode}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        if (!response.ok) {
            showAuthError(data.error || 'Authentication failed');
            return;
        }

        quizState.user = data;
        csrfToken = data.csrfToken || null;
        showStatusScreen();
    } catch (error) {
        console.error('Auth error:', error);
        showAuthError('Unable to authenticate. Please try again.');
    }
}

async function handleLogout() {
    try {
        const headers = {};
        if (csrfToken) {
            headers['X-CSRF-Token'] = csrfToken;
        }
        await fetch(`${API_BASE}/api/logout`, { method: 'POST', headers });
    } catch (error) {
        console.error('Logout error:', error);
    }
    quizState.user = null;
    csrfToken = null;
    showScreen('welcomeScreen');
}

async function logout() {
    await handleLogout();
}

// ==================== Quiz Flow ====================

function displayQuiz(data) {
    submitting = false;
    resetHintReviewState();
    quizState.currentQuizId = Number(data.id) || null;
    const initialImages = Array.isArray(data.images) && data.images.length >= 2
        ? data.images
        : getHintImageUrls(quizState.currentQuizId, data.hintDifficulty);
    updateHintDisplay(data.hint, data.hintDifficulty, data.remainingGuesses, {
        images: initialImages
    });
    renderQuizImages(initialImages);
    document.getElementById('answerInput').value = '';
    document.getElementById('answerInput').focus();
}

function getHintImageUrls(quizId, hintDifficulty) {
    const parsedQuizId = Number(quizId);
    const parsedDifficulty = Number(hintDifficulty);
    if (!Number.isFinite(parsedQuizId) || !Number.isFinite(parsedDifficulty)) {
        return [];
    }
    return [
        `/media/countries/${parsedQuizId}/${parsedDifficulty}a.jpg`,
        `/media/countries/${parsedQuizId}/${parsedDifficulty}b.jpg`
    ];
}

function renderQuizImages(images) {
    if (!Array.isArray(images) || images.length < 2) {
        return;
    }
    wireZoomableImage(document.getElementById('image1'), images[0], 'Destination image 1');
    wireZoomableImage(document.getElementById('image2'), images[1], 'Destination image 2');
}

async function loadQuestion() {
    try {
        const response = await fetch(`${API_BASE}/api/quiz`);
        if (!response.ok) {
            const error = await response.json();
            showNotification(error.error || 'Unable to load quiz.');
            return;
        }

        const data = await response.json();
        displayQuiz(data);
    } catch (error) {
        console.error('Error loading quiz:', error);
        showNotification('Failed to load quiz. Please refresh the page.');
    }
}

function updateHintDisplay(hintText, hintDifficulty, remainingGuesses, options = {}) {
    const difficulty = Number(hintDifficulty);
    const guesses = Number(remainingGuesses);

    if (!Number.isFinite(difficulty) || !Number.isFinite(guesses)) {
        document.getElementById('hint').textContent = hintText;
        updateHintProgressBar(null);
        updateNextHintCostPreview(null, null);
        updateRemainingGuessesDisplay(null);
        return;
    }

    updateHintProgressBar(difficulty);
    updateHintCounter(difficulty, guesses, options);
    updateNextHintCostPreview(difficulty, guesses);
    updateRemainingGuessesDisplay(guesses, options);
    addHintToHistory(hintText, difficulty, options.images);
    quizState.liveHintDifficulty = difficulty;
    quizState.liveRemainingGuesses = guesses;
    quizState.viewedHintDifficulty = difficulty;

    renderHintReviewControls();
    renderHintFromState();
}

function getDifficultyLabel(hintDifficulty) {
    const labels = {
        5: 'Hardest',
        4: 'Hard',
        3: 'Medium',
        2: 'Easy',
        1: 'Easiest'
    };

    return labels[hintDifficulty] || `Difficulty ${hintDifficulty}`;
}

function renderHintCounter(counterEl, difficulty, points) {
    const label = `${getDifficultyLabel(difficulty)} difficulty `;
    counterEl.innerHTML = `${label}<span class="current-hint-points">(${points}p)</span>`;
}

function updateHintCounter(hintDifficulty, remainingGuesses, options = {}) {
    const counterEl = document.getElementById('currentHint');
    if (!counterEl) {
        return;
    }

    const difficulty = Number(hintDifficulty);
    const guesses = Number(remainingGuesses);
    if (!Number.isFinite(difficulty) || !Number.isFinite(guesses)) {
        return;
    }

    const points = difficulty * guesses;
    const shouldAnimateEvaporation = Boolean(options.animatePointsEvaporation);

    if (hintCounterAnimationTimeout !== null) {
        clearTimeout(hintCounterAnimationTimeout);
        hintCounterAnimationTimeout = null;
    }

    const currentPoints = Number(counterEl.dataset.currentPoints);
    if (!shouldAnimateEvaporation || !Number.isFinite(currentPoints) || currentPoints === points) {
        const pointsEl = counterEl.querySelector('.current-hint-points');
        if (pointsEl) {
            pointsEl.classList.remove('points-evaporate-out', 'points-evaporate-in');
        }
        renderHintCounter(counterEl, difficulty, points);
        counterEl.dataset.currentPoints = String(points);
        return;
    }

    const pointsEl = counterEl.querySelector('.current-hint-points');
    if (!pointsEl) {
        renderHintCounter(counterEl, difficulty, points);
        counterEl.dataset.currentPoints = String(points);
        return;
    }

    pointsEl.classList.remove('points-evaporate-out', 'points-evaporate-in');
    void pointsEl.offsetWidth;
    pointsEl.classList.add('points-evaporate-out');

    hintCounterAnimationTimeout = window.setTimeout(() => {
        renderHintCounter(counterEl, difficulty, points);
        counterEl.dataset.currentPoints = String(points);
        const refreshedPointsEl = counterEl.querySelector('.current-hint-points');
        if (refreshedPointsEl) {
            refreshedPointsEl.classList.remove('points-evaporate-out');
            refreshedPointsEl.classList.add('points-evaporate-in');
        }

        window.setTimeout(() => {
            if (refreshedPointsEl) {
                refreshedPointsEl.classList.remove('points-evaporate-in');
            }
        }, COUNTER_PUFF_DURATION_MS);
        hintCounterAnimationTimeout = null;
    }, COUNTER_PUFF_DURATION_MS);
}

function updateHintProgressBar(hintDifficulty) {
    const progressFill = document.getElementById('progressFill');
    if (!progressFill) {
        return;
    }

    const difficulty = Number(hintDifficulty);
    if (!Number.isFinite(difficulty)) {
        progressFill.style.width = '0%';
        return;
    }

    const totalHints = Number(validationRules.destination?.hintCount) || 5;
    const normalizedDifficulty = Math.min(totalHints, Math.max(1, difficulty));
    const progressPercentage = (normalizedDifficulty / totalHints) * 100;
    const overlayPercentage = 100 - progressPercentage;
    progressFill.style.width = `${overlayPercentage}%`;
}

function updateNextHintCostPreview(hintDifficulty, remainingGuesses) {
    const previewEl = document.getElementById('nextHintCostPreview');
    if (!previewEl) {
        return;
    }

    const difficulty = Number(hintDifficulty);
    const guesses = Number(remainingGuesses);
    if (!Number.isFinite(difficulty) || !Number.isFinite(guesses)) {
        previewEl.textContent = '';
        return;
    }

    if (difficulty <= 1) {
        previewEl.textContent = 'No more hints, might as well guess now!';
        return;
    }

    const pointsGivenUp = difficulty > 1 ? guesses : 0;
    previewEl.textContent = `(-${pointsGivenUp}p)`;
}

function updateRemainingGuessesDisplay(remainingGuesses, options = {}) {
    const remainingGuessesEl = document.getElementById('remainingGuesses');
    if (!remainingGuessesEl) {
        return;
    }

    const guesses = Number(remainingGuesses);
    if (!Number.isFinite(guesses)) {
        remainingGuessesEl.textContent = '';
        remainingGuessesEl.classList.remove('remaining-guesses-evaporate-out', 'remaining-guesses-evaporate-in');
        delete remainingGuessesEl.dataset.currentGuesses;
        return;
    }

    const shouldAnimateEvaporation = Boolean(options.animatePointsEvaporation);

    if (remainingGuessesAnimationTimeout !== null) {
        clearTimeout(remainingGuessesAnimationTimeout);
        remainingGuessesAnimationTimeout = null;
    }

    const currentGuesses = Number(remainingGuessesEl.dataset.currentGuesses);
    if (!shouldAnimateEvaporation || !Number.isFinite(currentGuesses) || currentGuesses === guesses) {
        remainingGuessesEl.classList.remove('remaining-guesses-evaporate-out', 'remaining-guesses-evaporate-in');
        remainingGuessesEl.textContent = `Remaining guesses: ${guesses}`;
        remainingGuessesEl.dataset.currentGuesses = String(guesses);
        return;
    }

    remainingGuessesEl.classList.remove('remaining-guesses-evaporate-out', 'remaining-guesses-evaporate-in');
    void remainingGuessesEl.offsetWidth;
    remainingGuessesEl.classList.add('remaining-guesses-evaporate-out');

    remainingGuessesAnimationTimeout = window.setTimeout(() => {
        remainingGuessesEl.textContent = `Remaining guesses: ${guesses}`;
        remainingGuessesEl.dataset.currentGuesses = String(guesses);
        remainingGuessesEl.classList.remove('remaining-guesses-evaporate-out');
        remainingGuessesEl.classList.add('remaining-guesses-evaporate-in');

        window.setTimeout(() => {
            remainingGuessesEl.classList.remove('remaining-guesses-evaporate-in');
        }, COUNTER_PUFF_DURATION_MS);
        remainingGuessesAnimationTimeout = null;
    }, COUNTER_PUFF_DURATION_MS);
}

function resetHintReviewState() {
    quizState.hintHistory = {};
    quizState.hintImagesByDifficulty = {};
    quizState.unlockedHintDifficulties = [];
    quizState.liveHintDifficulty = null;
    quizState.liveRemainingGuesses = null;
    quizState.viewedHintDifficulty = null;

    const hintReviewSection = document.getElementById('hintReviewSection');
    const hintHistoryButtons = document.getElementById('hintHistoryButtons');
    const nextHintCostPreview = document.getElementById('nextHintCostPreview');
    const currentHint = document.getElementById('currentHint');
    const remainingGuesses = document.getElementById('remainingGuesses');
    if (hintCounterAnimationTimeout !== null) {
        clearTimeout(hintCounterAnimationTimeout);
        hintCounterAnimationTimeout = null;
    }
    if (remainingGuessesAnimationTimeout !== null) {
        clearTimeout(remainingGuessesAnimationTimeout);
        remainingGuessesAnimationTimeout = null;
    }
    if (hintReviewSection) {
        hintReviewSection.classList.add('hidden');
    }
    if (hintHistoryButtons) {
        hintHistoryButtons.innerHTML = '';
    }
    if (nextHintCostPreview) {
        nextHintCostPreview.textContent = '';
    }
    updateRemainingGuessesDisplay(null);
    updateHintProgressBar(null);
    if (currentHint) {
        const pointsEl = currentHint.querySelector('.current-hint-points');
        if (pointsEl) {
            pointsEl.classList.remove('points-evaporate-out', 'points-evaporate-in');
        }
        delete currentHint.dataset.currentPoints;
    }
    if (remainingGuesses) {
        remainingGuesses.classList.remove('remaining-guesses-evaporate-out', 'remaining-guesses-evaporate-in');
        delete remainingGuesses.dataset.currentGuesses;
    }
}

function addHintToHistory(hintText, hintDifficulty, hintImages) {
    if (!Number.isFinite(hintDifficulty) || hintDifficulty < 1) {
        return;
    }
    if (typeof hintText !== 'string') {
        return;
    }
    if (!(hintDifficulty in quizState.hintHistory)) {
        quizState.unlockedHintDifficulties.push(hintDifficulty);
        quizState.unlockedHintDifficulties.sort((a, b) => b - a);
    }
    quizState.hintHistory[hintDifficulty] = hintText;
    if (Array.isArray(hintImages) && hintImages.length >= 2) {
        quizState.hintImagesByDifficulty[hintDifficulty] = hintImages.slice(0, 2);
    }
}

function selectHintForReview(hintDifficulty) {
    if (!(hintDifficulty in quizState.hintHistory)) {
        return;
    }
    quizState.viewedHintDifficulty = hintDifficulty;
    renderHintReviewControls();
    renderHintFromState();
}

function renderHintReviewControls() {
    const hintReviewSection = document.getElementById('hintReviewSection');
    const hintHistoryButtons = document.getElementById('hintHistoryButtons');
    if (!hintReviewSection || !hintHistoryButtons) {
        return;
    }

    hintHistoryButtons.innerHTML = '';

    if (quizState.unlockedHintDifficulties.length <= 1) {
        hintReviewSection.classList.add('hidden');
        return;
    }

    hintReviewSection.classList.remove('hidden');
    quizState.unlockedHintDifficulties.forEach(difficulty => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'hint-history-btn';
        if (difficulty === quizState.viewedHintDifficulty) {
            button.classList.add('active');
        }

        const totalHints = Number(validationRules.destination?.hintCount) || 5;
        const ordinalPosition = (totalHints - difficulty) + 1;
        const labels = ['First', 'Second', 'Third', 'Fourth', 'Fifth'];
        const ordinalLabel = labels[ordinalPosition - 1] || `${ordinalPosition}th`;
        button.textContent = ordinalLabel;
        button.addEventListener('click', () => selectHintForReview(difficulty));
        hintHistoryButtons.appendChild(button);
    });
}

function renderHintFromState() {
    const viewedDifficulty = quizState.viewedHintDifficulty;
    const liveDifficulty = quizState.liveHintDifficulty;
    const remainingGuesses = quizState.liveRemainingGuesses;
    const viewedHintText = quizState.hintHistory[viewedDifficulty] || '';

    document.getElementById('hint').textContent = viewedHintText;

    if (!Number.isFinite(liveDifficulty) || !Number.isFinite(remainingGuesses)) {
        document.getElementById('hintProgress').textContent = '';
        document.getElementById('hintPoints').textContent = '';
        return;
    }

    document.getElementById('hintProgress').textContent = '';
    document.getElementById('hintPoints').textContent = '';

    const imagesForViewedHint = quizState.hintImagesByDifficulty[viewedDifficulty];
    if (Array.isArray(imagesForViewedHint) && imagesForViewedHint.length >= 2) {
        renderQuizImages(imagesForViewedHint);
        return;
    }

    const fallbackImages = getHintImageUrls(quizState.currentQuizId, viewedDifficulty);
    renderQuizImages(fallbackImages);
}

function renderImageGallery(container, imageUrls, variant = 'result') {
    if (!container) return;
    const images = Array.isArray(imageUrls) ? imageUrls.slice(0, 10) : [];
    container.innerHTML = '';

    if (images.length === 0) {
        container.classList.add('hidden');
        return;
    }

    container.classList.remove('hidden');
    images.forEach((url, index) => {
        const imageContainer = document.createElement('div');
        const image = document.createElement('img');

        if (variant === 'hint') {
            imageContainer.className = 'image-container';
            image.className = 'quiz-image';
        } else {
            imageContainer.className = 'result-image-container';
            image.className = 'result-image';
        }

        image.loading = 'lazy';
        wireZoomableImage(image, url, `Additional destination image ${index + 1}`);

        imageContainer.appendChild(image);
        container.appendChild(imageContainer);
    });
}

function renderResultImages(imageUrls) {
    const container = document.getElementById('resultImages');
    renderImageGallery(container, imageUrls);
}

async function submitAnswer() {
    if (submitting) return;

    const answerInput = document.getElementById('answerInput');
    const userAnswer = answerInput.value.trim();
    if (!userAnswer) {
        animateWrongGuess(answerInput);
        answerInput.focus();
        return;
    }

    submitting = true;
    try {
        const response = await fetch(`${API_BASE}/api/check-answer`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ answer: userAnswer })
        });

        const result = await response.json();
        if (!response.ok) {
            showNotification(result.error || 'Error checking answer');
            submitting = false;
            return;
        }

        if (result.correct) {
            showFeedback(true, result.points, result.answer, result.resultImages || []);
        } else if (result.remainingGuesses !== undefined && result.remainingGuesses > 0) {
            // Wrong but still has guesses — backend returned next hint
            animateWrongGuess(answerInput);
            const nextHintImages = Array.isArray(result.images) && result.images.length >= 2
                ? result.images
                : getHintImageUrls(quizState.currentQuizId, result.hintDifficulty);
            updateHintDisplay(result.hint, result.hintDifficulty, result.remainingGuesses, {
                animatePointsEvaporation: true,
                images: nextHintImages
            });
            renderQuizImages(nextHintImages);
            document.getElementById('answerInput').value = '';
            document.getElementById('answerInput').focus();
            submitting = false;
        } else {
            // Out of guesses
            showFeedback(false, 0, result.answer, result.resultImages || []);
        }
    } catch (error) {
        console.error('Error checking answer:', error);
        showNotification('Error checking answer');
        submitting = false;
    }
}

async function nextHint() {
    await fetchHint();
}

async function fetchHint() {
    document.getElementById('hint').textContent = 'Loading hint...';
    try {
        const response = await fetch(`${API_BASE}/api/hint`);
        const result = await response.json();
        if (!response.ok) {
            if (response.status === 404) {
                document.getElementById('hint').textContent = 'No more hints remaining, you might as well guess now!';
                document.getElementById('hintProgress').textContent = '';
                document.getElementById('hintPoints').textContent = '';
                return;
            }
            throw new Error(result.error || 'Failed to fetch hint');
        }
        const nextHintImages = Array.isArray(result.images) && result.images.length >= 2
            ? result.images
            : getHintImageUrls(quizState.currentQuizId, result.hintDifficulty);
        updateHintDisplay(result.hint, result.hintDifficulty, result.remainingGuesses, {
            images: nextHintImages
        });
        renderQuizImages(nextHintImages);
        document.getElementById('answerInput').value = '';
        document.getElementById('answerInput').focus();
    } catch (error) {
        console.error('Error fetching hint:', error);
        document.getElementById('hint').textContent = 'Error loading hint. Please try again.';
    }
}

function showFeedback(isCorrect, points, correctAnswer, resultImages = []) {
    showScreen('feedbackScreen');

    const feedbackStatus = document.getElementById('feedbackStatus');
    const feedbackDetails = document.getElementById('feedbackDetails');

    if (isCorrect) {
        feedbackStatus.textContent = '✓ Correct!';
        feedbackStatus.className = 'feedback-status correct';
        feedbackDetails.innerHTML = `
            <p>The destination was: <span class="correct-answer">${correctAnswer}</span></p>
            <p class="points-earned">${points} Points!</p>
        `;
    } else {
        feedbackStatus.textContent = '✗ Incorrect';
        feedbackStatus.className = 'feedback-status incorrect';
        feedbackDetails.innerHTML = `
            <p>The destination was: <span class="correct-answer">${correctAnswer}</span></p>
            <p class="points-earned">0 Points</p>
        `;
    }

    // Store points in a data attribute for the results screen
    document.getElementById('feedbackScreen').dataset.lastScore = points;
    document.getElementById('feedbackScreen').dataset.resultImages = JSON.stringify(resultImages);

    const feedbackImagesHeading = document.getElementById('feedbackResultImagesHeading');
    const feedbackImagesContainer = document.getElementById('feedbackResultImages');
    if (feedbackImagesHeading) {
        if (Array.isArray(resultImages) && resultImages.length > 0) {
            feedbackImagesHeading.textContent = `Here are some extra pictures from ${correctAnswer}`;
            feedbackImagesHeading.classList.remove('hidden');
        } else {
            feedbackImagesHeading.textContent = '';
            feedbackImagesHeading.classList.add('hidden');
        }
    }
    renderImageGallery(feedbackImagesContainer, resultImages, 'hint');
}

function endQuiz() {
    showScreen('resultsScreen');
    const feedbackScreen = document.getElementById('feedbackScreen');
    const score = parseInt(document.getElementById('feedbackScreen').dataset.lastScore || '0', 10);
    let resultImages = [];
    try {
        resultImages = JSON.parse(feedbackScreen.dataset.resultImages || '[]');
    } catch (_error) {
        resultImages = [];
    }

    document.getElementById('finalScore').textContent = score;

    let message = '';
    if (score >= 15) {
        message = '🌟 Outstanding! You are a true travel expert!';
    } else if (score >= 12) {
        message = '🎉 Excellent! You know your destinations well!';
    } else if (score >= 9) {
        message = '👏 Good job! Keep exploring the world!';
    } else if (score >= 6) {
        message = '📚 Not bad! Time to travel more!';
    } else {
        message = '🗺️ Keep learning about travel destinations!';
    }

    document.getElementById('resultsMessage').textContent = message;
    renderResultImages(resultImages);
}

function retakeQuiz() {
    showScreen('quizScreen');
    loadQuestion();
}

// ==================== Status Screen ====================

async function showStatusScreen() {
    showScreen('statusScreen');
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

    // Show/hide admin link based on user role
    const adminLink = document.getElementById('adminLink');
    if (adminLink) {
        if (quizState.user && quizState.user.isAdmin) {
            adminLink.style.display = '';
        } else {
            adminLink.style.display = 'none';
        }
    }

    // Fetch and render quiz type buttons
    await loadQuizTypeButtons();
}

async function loadQuizTypeButtons() {
    // Hide the static "Run Random Quiz" button
    const staticRunBtn = document.getElementById('runRandomQuizBtn');
    if (staticRunBtn) {
        staticRunBtn.style.display = 'none';
    }

    // Find or create the quiz type buttons container
    let quizTypeContainer = document.getElementById('quizTypeButtonsContainer');
    if (!quizTypeContainer) {
        quizTypeContainer = document.createElement('div');
        quizTypeContainer.id = 'quizTypeButtonsContainer';
        quizTypeContainer.className = 'quiz-type-buttons-container';
        // Insert before the admin link button
        const quizActions = document.querySelector('.quiz-actions');
        const adminLinkEl = quizActions ? quizActions.querySelector('#adminLink') : null;
        if (quizActions && adminLinkEl) {
            quizActions.insertBefore(quizTypeContainer, adminLinkEl);
        } else if (quizActions && staticRunBtn && staticRunBtn.parentNode === quizActions) {
            quizActions.insertBefore(quizTypeContainer, staticRunBtn.nextSibling);
        } else if (quizActions) {
            quizActions.appendChild(quizTypeContainer);
        }
    }

    // Clear previous content
    quizTypeContainer.innerHTML = '';

    try {
        const response = await fetch(`${API_BASE}/api/quiz-types`);
        if (!response.ok) {
            showNotification('Could not load quiz types.');
            return;
        }

        const quizTypes = await response.json();

        if (quizTypes.length === 0) {
            quizTypeContainer.innerHTML = '<p class="quiz-type-empty-message">No quiz types are currently available.</p>';
            return;
        }

        // Sort alphabetically by displayName
        quizTypes.sort((a, b) => a.displayName.localeCompare(b.displayName));

        // Render one button per quiz type with adjacent info icon
        quizTypes.forEach(type => {
            const row = document.createElement('div');
            row.className = 'quiz-type-row';

            const btn = document.createElement('button');
            btn.className = 'btn btn-primary quiz-type-btn';
            btn.textContent = type.displayName;
            btn.addEventListener('click', () => runRandomQuiz());

            const infoBtn = document.createElement('button');
            infoBtn.className = 'btn btn-secondary quiz-type-info-btn';
            infoBtn.setAttribute('aria-label', `Rules for ${type.displayName}`);
            infoBtn.textContent = 'ℹ️';
            infoBtn.addEventListener('click', () => openRulesModal(type.identifier));

            row.appendChild(btn);
            row.appendChild(infoBtn);
            quizTypeContainer.appendChild(row);
        });
    } catch (error) {
        console.error('Error loading quiz types:', error);
        showNotification('Could not load quiz types.');
    }
}

function backToStatus() {
    showStatusScreen();
}

async function runRandomQuiz() {
    showScreen('quizScreen');
    loadQuestion();
}

async function runSpecificQuiz() {
    const quizId = document.getElementById('specificQuizId').value.trim();
    if (!quizId) {
        showNotification('Please enter a quiz ID.');
        return;
    }
    try {
        const response = await fetch(`${API_BASE}/api/quiz/${quizId}`);
        if (!response.ok) {
            const err = await response.json();
            showNotification(err.error || 'Quiz not found.');
            return;
        }
        const data = await response.json();
        showScreen('quizScreen');
        displayQuiz(data);
    } catch (error) {
        console.error('Error starting specific quiz:', error);
        showNotification('Failed to load quiz.');
    }
}

// ==================== Wrong Guess Animation ====================

/**
 * Applies wrong-guess animation to the quiz screen container.
 * - If prefers-reduced-motion is active: applies static red border for 1s.
 * - Otherwise: applies shake + glow CSS animations (800ms).
 * - Handles re-triggering if animation is already active.
 * - Cleans up all animation classes/styles on completion.
 *
 * @param {HTMLElement} inputElement - The input element (used for fallback/focus, animation targets #quizScreen)
 */
function animateWrongGuess(inputElement) {
    if (!inputElement) return;

    const target = document.getElementById('quizScreen') || inputElement;
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (prefersReducedMotion) {
        // Static fallback: two-pulse glow animation (1.2s)
        target.classList.remove('screen-fade-in');
        target.classList.remove('wrong-guess-static');
        void target.offsetWidth;
        target.classList.add('wrong-guess-static');
        setTimeout(() => {
            target.classList.remove('wrong-guess-static');
        }, 1300);
        return;
    }

    // Remove fade-in animation class to avoid conflict with wrong-guess animation
    target.classList.remove('screen-fade-in');

    // Remove existing animation classes to allow re-trigger
    target.classList.remove('wrong-guess-shake', 'wrong-guess-glow');

    // Force reflow so re-adding classes restarts the animation
    void target.offsetWidth;

    // Apply animation classes
    target.classList.add('wrong-guess-shake', 'wrong-guess-glow');

    // Cleanup function to remove classes and residual inline styles
    function cleanup() {
        target.classList.remove('wrong-guess-shake', 'wrong-guess-glow');
        target.style.removeProperty('left');
        target.style.removeProperty('transform');
        target.style.removeProperty('box-shadow');
        target.style.removeProperty('border-color');
        target.style.removeProperty('position');
    }

    // Listen for animationend to remove classes (once)
    let cleaned = false;
    function onAnimationEnd(e) {
        // Only respond to animations on the target itself, not bubbled from children
        if (e.target !== target) return;
        if (cleaned) return;
        cleaned = true;
        cleanup();
    }

    target.addEventListener('animationend', onAnimationEnd);

    // Defensive fallback: remove classes after 1500ms if animationend never fires
    setTimeout(() => {
        if (!cleaned) {
            cleaned = true;
            target.removeEventListener('animationend', onAnimationEnd);
            cleanup();
        }
    }, 1500);
}

// ==================== Initialization ====================

// Allow Enter key to submit answer
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('answerInput')?.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            submitAnswer();
        }
    });

    document.getElementById('email')?.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            handleAuth();
        }
    });

    // Show validation styling after the user interacts with the email field
    const emailInput = document.getElementById('email');
    emailInput?.addEventListener('blur', () => {
        emailInput.classList.add('touched');
        const hint = document.getElementById('emailHint');
        if (hint) {
            hint.style.display = emailInput.validity.valid || !emailInput.value ? 'none' : 'block';
        }
    });
    emailInput?.addEventListener('input', () => {
        if (emailInput.classList.contains('touched')) {
            const hint = document.getElementById('emailHint');
            if (hint) {
                hint.style.display = emailInput.validity.valid || !emailInput.value ? 'none' : 'block';
            }
        }
    });

    document.getElementById('password')?.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            handleAuth();
        }
    });

    loadValidationRules();
    loadUser();
});
