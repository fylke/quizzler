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
            const restoredGuest = await restoreGuestSession();
            if (restoredGuest) {
                const restoredActiveQuiz = await restoreActiveQuiz();
                if (!restoredActiveQuiz) {
                    if (suppressNextAutoStatusScreen) {
                        suppressNextAutoStatusScreen = false;
                    } else {
                        showStatusScreen();
                    }
                }
                return;
            }
            const startedGuest = await continueAsGuest(true);
            if (!startedGuest) {
                toggleAuthMode('login');
                showScreen('welcomeScreen');
            }
            return;
        }
        if (!response.ok) {
            showNotification('Unable to reach server. Please try again.');
            showScreen('welcomeScreen');
            return;
        }
        const data = await response.json();
        quizState.user = data;
        quizState.isGuest = false;
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

async function restoreGuestSession() {
    try {
        const response = await fetch(`${API_BASE}/api/guest-session`);
        if (response.status === 404) {
            return false;
        }
        if (!response.ok) {
            return false;
        }

        const data = await response.json();
        applyGuestSession(data);
        return true;
    } catch (error) {
        console.error('Guest restore error:', error);
        return false;
    }
}

function applyGuestSession(data) {
    quizState.user = data.guest || null;
    quizState.isGuest = true;
    csrfToken = null;
}

async function continueAsGuest(isAutoStart = false) {
    try {
        const response = await fetch(`${API_BASE}/api/guest-session`, {
            method: 'POST',
            credentials: 'same-origin'
        });

        if (!response.ok) {
            let errorMessage = 'Unable to start guest session. Please try again.';
            try {
                const errorPayload = await response.json();
                if (typeof errorPayload?.error === 'string' && errorPayload.error.trim()) {
                    errorMessage = errorPayload.error;
                }
            } catch (parseError) {
                // Ignore non-JSON error responses and keep the generic message.
            }
            showNotification(errorMessage);
            return false;
        }

        const data = await response.json();
        applyGuestSession(data);

        const restoredActiveQuiz = await restoreActiveQuiz();
        if (!restoredActiveQuiz) {
            if (isAutoStart && suppressNextAutoStatusScreen) {
                suppressNextAutoStatusScreen = false;
            } else {
                showStatusScreen();
            }
        }
        return true;
    } catch (error) {
        console.error('Guest session error:', error);
        showNotification('Unable to continue as guest.');
        return false;
    }
}

function openLoginFromStatus() {
    showRegisteredScreen('auth', 'login');
}

function openCreateAccountFromGuestBanner() {
    showRegisteredScreen('auth', 'register');
}

function updateGuestUpgradeVisibility() {
    const guestRestrictions = document.getElementById('guestRestrictionsStatus');

    if (guestRestrictions) {
        if (quizState.isGuest) {
            guestRestrictions.classList.remove('hidden');
        } else {
            guestRestrictions.classList.add('hidden');
        }
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
    const authButton = document.getElementById('authButton');
    const nameInput = document.getElementById('name');
    const switchToRegister = document.getElementById('switchToRegister');
    const switchToLogin = document.getElementById('switchToLogin');
    const authHeading = document.getElementById('authHeading');
    const authSubtext = document.getElementById('authSubtext');

    if (mode === 'register') {
        authButton.textContent = 'Create Account';
        if (nameInput) {
            nameInput.classList.remove('hidden');
        }
        switchToRegister.classList.add('hidden');
        switchToLogin.classList.remove('hidden');
        authHeading.textContent = 'Quizzler';
        authSubtext.textContent = 'Register and start the quiz.';
        updatePasswordStrength();
    } else {
        authButton.textContent = 'Log In';
        if (nameInput) {
            nameInput.classList.add('hidden');
            nameInput.value = '';
        }
        switchToRegister.classList.remove('hidden');
        switchToLogin.classList.add('hidden');
        authHeading.textContent = 'Quizzler';
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
    const name = document.getElementById('name')?.value.trim() || '';
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value.trim();

    document.getElementById('email').classList.add('touched');

    if (!email || !password) {
        showAuthError('Please fill in all required fields.');
        return;
    }

    if (authMode === 'register' && password.length < validationRules.password.minLength) {
        showAuthError(`Password must be at least ${validationRules.password.minLength} characters.`);
        return;
    }

    if (authMode === 'register' && !name) {
        showAuthError('Please provide your name.');
        return;
    }

    const emailInput = document.getElementById('email');
    if (!emailInput.validity.valid) {
        showAuthError('Please enter a valid email address.');
        return;
    }

    clearAuthError();

    const payload = authMode === 'register'
        ? { name, email, password }
        : { email, password };

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
        quizState.isGuest = false;
        csrfToken = data.csrfToken || null;
        updateGuestUpgradeVisibility();
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
    quizState.isGuest = false;
    csrfToken = null;
    updateGuestUpgradeVisibility();
    showScreen('welcomeScreen');
}

async function logout() {
    await handleLogout();
}

// ==================== Main + Stats Screens ====================

async function showMainScreen() {
    await showRegisteredScreen('main');
}

async function showStatusScreen() {
    await showRegisteredScreen('main');
}

async function showStatsScreen() {
    await showRegisteredScreen('stats');
}

function updateMainCornerIconVisibility() {
    const statusLoginLink = document.getElementById('statusLoginLink');
    const statsBtn = document.getElementById('statsBtn');
    const adminLink = document.getElementById('adminLink');
    const logoutBtn = document.getElementById('logoutBtn');

    const isGuestOrAnonymous = quizState.isGuest || !quizState.user;
    const isAdminUser = Boolean(quizState.user && quizState.user.isAdmin && !quizState.isGuest);

    if (statusLoginLink) {
        statusLoginLink.classList.toggle('hidden', !isGuestOrAnonymous);
    }

    if (statsBtn) {
        statsBtn.style.display = '';
    }

    if (adminLink) {
        adminLink.style.display = isAdminUser ? '' : 'none';
    }

    if (logoutBtn) {
        logoutBtn.style.display = isGuestOrAnonymous ? 'none' : '';
    }
}

async function loadQuizTypeButtons() {
    const staticRunBtn = document.getElementById('runRandomQuizBtn');
    if (staticRunBtn) {
        staticRunBtn.style.display = 'none';
    }

    let quizTypeContainer = document.getElementById('quizTypeButtonsContainer');
    const quizActions = document.querySelector('.quiz-actions');
    if (!quizTypeContainer) {
        quizTypeContainer = document.createElement('div');
        quizTypeContainer.id = 'quizTypeButtonsContainer';
        quizTypeContainer.className = 'quiz-type-buttons-container';
        if (quizActions && quizActions.firstChild) {
            quizActions.insertBefore(quizTypeContainer, quizActions.firstChild);
        } else if (quizActions) {
            quizActions.appendChild(quizTypeContainer);
        }
    }

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

        quizTypes.sort((a, b) => a.displayName.localeCompare(b.displayName));

        quizTypes.forEach(type => {
            const row = document.createElement('div');
            row.className = 'quiz-type-row';

            const btn = document.createElement('button');
            btn.className = 'btn btn-primary quiz-type-btn';
            btn.textContent = type.displayName;
            if (type.identifier === 'countries') {
                btn.title = 'Guess the country based on a text- and two picture hints. You have 5 hint levels and 3 guesses.';
            }
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
    showRegisteredScreen('main');
}