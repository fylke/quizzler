// Quiz state keeps minimal client-side UI state. Scoring/progression remains backend-owned.
let quizState = {
    user: null,
    isGuest: false,
    currentQuizId: null,
    hintHistory: {},
    currentHint: {
        difficulty: null,
        remainingGuesses: null,
        viewedDifficulty: null
    }
};

let csrfToken = null;

const API_BASE = window.location.origin;
let authMode = 'login';
let suppressNextAutoStatusScreen = false;
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

const appState = {};
Object.defineProperties(appState, {
    quizState: {
        get() {
            return quizState;
        },
        set(value) {
            quizState = value;
        }
    },
    csrfToken: {
        get() {
            return csrfToken;
        },
        set(value) {
            csrfToken = value;
        }
    },
    validationRules: {
        get() {
            return validationRules;
        },
        set(value) {
            validationRules = value;
        }
    },
    authMode: {
        get() {
            return authMode;
        },
        set(value) {
            authMode = value;
        }
    }
});

window.QuizzlerApp = {
    state: appState,
    api: {
        baseUrl: API_BASE
    },
    screens: {
        get(name) {
            return getScreenController(name);
        },
        show(...args) {
            return showRegisteredScreen(...args);
        }
    },
    ui: {
        showScreen,
        showNotification,
        showStatusScreen(...args) {
            return showStatusScreen(...args);
        }
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

function bindClick(elementId, handler, options = {}) {
    const element = document.getElementById(elementId);
    if (!element) {
        return;
    }

    element.addEventListener('click', (event) => {
        if (options.preventDefault) {
            event.preventDefault();
        }
        handler(event);
    });
}

function bindAuthAndMainScreenActions() {
    bindClick('authButton', () => {
        handleAuth();
    });
    bindClick('guestButton', () => {
        continueAsGuest();
    });
    bindClick('switchToRegisterLink', () => {
        toggleAuthMode('register');
    }, { preventDefault: true });
    bindClick('switchToLoginLink', () => {
        toggleAuthMode('login');
    }, { preventDefault: true });
    bindClick('forgotPasswordLink', () => {
        openForgotPasswordModal();
    }, { preventDefault: true });
    bindClick('adminLink', () => {
        showAdminScreen();
    });
    bindClick('statsBtn', () => {
        showStatsScreen();
    });
    bindClick('statusLoginLink', () => {
        openLoginFromStatus();
    }, { preventDefault: true });
    bindClick('logoutBtn', () => {
        handleLogout();
    });
    bindClick('runRandomQuizBtn', () => {
        runRandomQuiz();
    });
    bindClick('runSpecificQuizBtn', () => {
        runSpecificQuiz();
    });
    bindClick('guestCreateAccountLink', () => {
        openCreateAccountFromGuestBanner();
    }, { preventDefault: true });
    bindClick('backToMainFromStatsBtn', () => {
        backToStatus();
    });
    bindClick('submitAnswerBtn', () => {
        submitAnswer();
    });
    bindClick('nextHintBtn', () => {
        nextHint();
    });
    bindClick('backToMainFromResultsBtn', () => {
        backToStatus();
    });
}

async function runRandomQuiz() {
    await getScreenController('quiz').startRandomQuiz();
}

async function runSpecificQuiz() {
    const quizId = document.getElementById('specificQuizId').value.trim();
    if (!/^[1-9]\d*$/.test(quizId)) {
        showNotification('Quiz not found');
        return;
    }
    try {
        const response = await fetch(`${API_BASE}/api/quiz/${quizId}`);
        if (!response.ok) {
            showNotification('Quiz not found');
            return;
        }
        const data = await response.json();
        getScreenController('quiz').showSpecificQuiz(data);
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
 * @returns {Promise<void>} Resolves after animation cleanup has completed.
 */
function animateWrongGuess(inputElement) {
    return new Promise(resolve => {
        if (!inputElement) {
            resolve();
            return;
        }

        const target = document.getElementById('quizScreen') || inputElement;
        const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        let resolved = false;
        function finish() {
            if (resolved) {
                return;
            }
            resolved = true;
            resolve();
        }

        if (prefersReducedMotion) {
            // Static fallback: two-pulse glow animation (1.2s)
            target.classList.remove('screen-fade-in');
            target.classList.remove('wrong-guess-static');
            void target.offsetWidth;
            target.classList.add('wrong-guess-static');
            setTimeout(() => {
                target.classList.remove('wrong-guess-static');
                finish();
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
        function finishAnimation() {
            if (cleaned) {
                return;
            }
            cleaned = true;
            target.removeEventListener('animationend', onAnimationEnd);
            cleanup();
            finish();
        }
        function onAnimationEnd(e) {
            // Only respond to animations on the target itself, not bubbled from children
            if (e.target !== target) return;
            finishAnimation();
        }

        target.addEventListener('animationend', onAnimationEnd);

        // Defensive fallback: remove classes after 1500ms if animationend never fires
        setTimeout(() => {
            finishAnimation();
        }, 1500);
    });
}

// ==================== Initialization ====================

// Allow Enter key to submit answer
document.addEventListener('DOMContentLoaded', () => {
    bindAuthAndMainScreenActions();

    document.getElementById('answerInput')?.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            submitAnswer();
        }
    });

    document.getElementById('specificQuizId')?.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            runSpecificQuiz();
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
    document.getElementById('password')?.addEventListener('input', () => {
        updatePasswordStrength();
    });

    loadValidationRules();
    loadUser();
});
