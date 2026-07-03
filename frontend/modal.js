// ==================== Generic Focus Trap ====================

/**
 * Set up a focus trap and Escape-to-close handler for a modal element.
 *
 * @param {string} modalId - The DOM id of the modal container
 * @param {function} closeCallback - Function to call when Escape is pressed or focus leaves the modal
 * @param {string[]|null} [focusableIds] - Optional explicit list of element IDs to cycle through.
 *   If null, all visible focusable elements inside the modal are used.
 */
function setupFocusTrap(modalId, closeCallback, focusableIds) {
    document.addEventListener('keydown', function (e) {
        const modal = document.getElementById(modalId);
        if (!modal || modal.style.display === 'none') return;

        if (e.key === 'Escape') {
            e.preventDefault();
            closeCallback();
            return;
        }

        if (e.key === 'Tab') {
            let focusableElements;

            if (focusableIds) {
                focusableElements = focusableIds
                    .map(id => document.getElementById(id))
                    .filter(el => el && el.offsetParent !== null);
            } else {
                const selectors = 'a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';
                focusableElements = Array.from(modal.querySelectorAll(selectors))
                    .filter(el => el.offsetParent !== null);
            }

            if (focusableElements.length === 0) return;

            const firstEl = focusableElements[0];
            const lastEl = focusableElements[focusableElements.length - 1];

            if (e.shiftKey) {
                if (document.activeElement === firstEl) {
                    e.preventDefault();
                    lastEl.focus();
                }
            } else {
                if (document.activeElement === lastEl) {
                    e.preventDefault();
                    firstEl.focus();
                }
            }
        }
    });
}

function wireZoomableImage(imageEl, imageUrl, altText) {
    if (!imageEl) {
        return;
    }

    imageEl.src = imageUrl;
    imageEl.alt = altText;
    imageEl.tabIndex = 0;
    imageEl.setAttribute('role', 'button');
    imageEl.setAttribute('aria-label', `${altText}. Click to enlarge.`);
    imageEl.title = 'Click to enlarge';

    const applyOrientationClass = () => {
        imageEl.classList.remove('is-portrait', 'is-landscape');
        if (imageEl.naturalHeight > imageEl.naturalWidth) {
            imageEl.classList.add('is-portrait');
            return;
        }
        imageEl.classList.add('is-landscape');
    };

    imageEl.onload = applyOrientationClass;
    if (imageEl.complete && imageEl.naturalWidth > 0 && imageEl.naturalHeight > 0) {
        applyOrientationClass();
    }

    imageEl.onclick = function () {
        openImageModal(imageUrl, altText);
    };

    imageEl.onkeydown = function (event) {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            openImageModal(imageUrl, altText);
        }
    };
}

// ==================== Rules Modal ====================

let _rulesModalTrigger = null;

async function openRulesModal(quizType) {
    // Store reference to triggering element for focus restoration
    _rulesModalTrigger = document.activeElement;

    const modal = document.getElementById('rulesModal');
    const titleEl = document.getElementById('rulesModalTitle');
    const contentEl = document.getElementById('rulesModalContent');

    // The markdown content already includes its own heading.
    titleEl.textContent = '';
    contentEl.innerHTML = '<p class="rules-loading">Loading...</p>';
    modal.style.display = 'flex';

    // Fetch rules content
    try {
        const response = await fetch(`${API_BASE}/api/rules/${encodeURIComponent(quizType)}`);
        if (!response.ok) {
            // Hide modal and notify user
            modal.style.display = 'none';
            const errData = await response.json().catch(() => ({}));
            showNotification(errData.error || 'Could not load rules.');
            if (_rulesModalTrigger) _rulesModalTrigger.focus();
            return;
        }

        const data = await response.json();
        contentEl.innerHTML = renderMarkdown(data.content);
    } catch (error) {
        console.error('Error fetching rules:', error);
        modal.style.display = 'none';
        showNotification('Could not load rules.');
        if (_rulesModalTrigger) _rulesModalTrigger.focus();
        return;
    }

    // Focus the close button
    const closeBtn = document.getElementById('rulesModalCloseBtn');
    if (closeBtn) closeBtn.focus();
}

function closeRulesModal() {
    const modal = document.getElementById('rulesModal');
    modal.style.display = 'none';

    // Return focus to the element that triggered the modal
    if (_rulesModalTrigger) {
        _rulesModalTrigger.focus();
        _rulesModalTrigger = null;
    }
}

// ==================== Hint Complaint Modal ====================

let _hintComplaintTrigger = null;
const _HINT_COMPLAINT_EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function openHintComplaintModal() {
    const quizId = quizState.currentQuizId;
    const hintDifficulty = quizState.viewedHintDifficulty || quizState.liveHintDifficulty;

    if (!Number.isFinite(quizId) || !Number.isFinite(hintDifficulty)) {
        showNotification('No active hint is available to report.', 'info');
        return;
    }

    _hintComplaintTrigger = document.activeElement;

    const modal = document.getElementById('hintComplaintModal');
    const quizIdEl = document.getElementById('hintComplaintQuizId');
    const hintLevelEl = document.getElementById('hintComplaintHintLevel');
    const emailEl = document.getElementById('hintComplaintEmail');
    const messageEl = document.getElementById('hintComplaintMessage');
    const errorEl = document.getElementById('hintComplaintError');

    quizIdEl.textContent = String(quizId);
    hintLevelEl.textContent = String(hintDifficulty);
    emailEl.value = (quizState.user && quizState.user.email) ? quizState.user.email : '';
    messageEl.value = '';
    errorEl.textContent = '';
    modal.dataset.quizId = String(quizId);
    modal.dataset.hintDifficulty = String(hintDifficulty);
    modal.style.display = 'flex';

    emailEl.focus();
}

function closeHintComplaintModal() {
    const modal = document.getElementById('hintComplaintModal');
    modal.style.display = 'none';

    if (_hintComplaintTrigger) {
        _hintComplaintTrigger.focus();
        _hintComplaintTrigger = null;
    }
}

async function handleHintComplaintSubmit() {
    const modal = document.getElementById('hintComplaintModal');
    const errorEl = document.getElementById('hintComplaintError');
    const emailEl = document.getElementById('hintComplaintEmail');
    const messageEl = document.getElementById('hintComplaintMessage');
    const sendBtn = document.getElementById('hintComplaintSendBtn');
    const quizId = Number(modal.dataset.quizId);
    const hintDifficulty = Number(modal.dataset.hintDifficulty);
    const complainerEmail = emailEl.value.trim().toLowerCase();
    const message = messageEl.value.trim();

    errorEl.textContent = '';

    if (!complainerEmail) {
        errorEl.textContent = 'Please provide your email so admins can respond.';
        emailEl.focus();
        return;
    }

    if (!_HINT_COMPLAINT_EMAIL_RE.test(complainerEmail)) {
        errorEl.textContent = 'Please enter a valid email address.';
        emailEl.focus();
        return;
    }

    if (!message) {
        errorEl.textContent = 'Please describe what is wrong with the hint.';
        messageEl.focus();
        return;
    }

    sendBtn.disabled = true;
    try {
        const response = await fetch(`${API_BASE}/api/hint-complaint`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                quizId,
                hintDifficulty,
                complainerEmail,
                message
            })
        });

        const result = await response.json();
        if (!response.ok) {
            errorEl.textContent = result.error || 'Failed to send complaint.';
            return;
        }

        closeHintComplaintModal();
        showNotification('Hint complaint sent to admins.', 'info');
    } catch (error) {
        console.error('Hint complaint error:', error);
        errorEl.textContent = 'Failed to send complaint.';
    } finally {
        sendBtn.disabled = false;
    }
}

// ==================== Forgot Password Modal ====================

const _FORGOT_EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function openForgotPasswordModal() {
    const modal = document.getElementById('forgotPasswordModal');
    const emailInput = document.getElementById('resetEmail');
    const errorEl = document.getElementById('resetEmailError');

    // Clear prior state
    emailInput.value = '';
    errorEl.textContent = '';

    // Show modal
    modal.style.display = 'flex';

    // Reset to form view (in case a confirmation message was previously shown)
    const formGroup = modal.querySelector('.modal-form-group');
    const buttons = modal.querySelector('.modal-buttons');
    if (formGroup) formGroup.style.display = '';
    if (buttons) buttons.style.display = '';
    const confirmationMsg = document.getElementById('forgotPasswordConfirmation');
    if (confirmationMsg) confirmationMsg.remove();

    // Focus on email input
    emailInput.focus();
}

function closeForgotPasswordModal() {
    const modal = document.getElementById('forgotPasswordModal');
    modal.style.display = 'none';

    // Return focus to the "Forgot password?" link
    const link = document.getElementById('forgotPasswordLink');
    if (link) link.focus();
}

async function handleForgotPasswordSubmit() {
    const emailInput = document.getElementById('resetEmail');
    const errorEl = document.getElementById('resetEmailError');
    const email = emailInput.value.trim();

    // Clear previous error
    errorEl.textContent = '';

    // Validate: non-empty
    if (!email) {
        errorEl.textContent = 'Please enter your email address.';
        emailInput.focus();
        return;
    }

    // Validate: valid format
    if (!_FORGOT_EMAIL_RE.test(email)) {
        errorEl.textContent = 'Please enter a valid email address.';
        emailInput.focus();
        return;
    }

    // Submit to backend
    try {
        const response = await fetch(`${API_BASE}/api/forgot-password`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });

        if (response.status === 500) {
            errorEl.textContent = 'Failed to send reset email. Please try again later.';
            return;
        }

        // For any valid-format email (200 or other non-500), show confirmation
        _showForgotPasswordConfirmation();
    } catch (error) {
        console.error('Forgot password error:', error);
        errorEl.textContent = 'Failed to send reset email. Please try again later.';
    }
}

function _showForgotPasswordConfirmation() {
    const modal = document.getElementById('forgotPasswordModal');
    const formGroup = modal.querySelector('.modal-form-group');
    const buttons = modal.querySelector('.modal-buttons');

    // Hide the form elements
    if (formGroup) formGroup.style.display = 'none';
    if (buttons) buttons.style.display = 'none';

    // Show confirmation message
    const confirmation = document.createElement('div');
    confirmation.id = 'forgotPasswordConfirmation';
    confirmation.className = 'modal-confirmation';
    confirmation.innerHTML = `
        <p>If that email is registered, a reset link has been sent.</p>
        <button onclick="closeForgotPasswordModal()" class="btn btn-primary">Close</button>
    `;
    modal.querySelector('.modal-card').appendChild(confirmation);
}

// ==================== Initialize Focus Traps ====================

// Rules modal: use generic focusable element detection
setupFocusTrap('rulesModal', closeRulesModal, null);

// Forgot password modal: explicit element IDs
setupFocusTrap('forgotPasswordModal', closeForgotPasswordModal, [
    'resetEmail', 'forgotPasswordSubmitBtn', 'forgotPasswordCancelBtn'
]);

setupFocusTrap('hintComplaintModal', closeHintComplaintModal, [
    'hintComplaintEmail', 'hintComplaintMessage', 'hintComplaintSendBtn', 'hintComplaintCancelBtn'
]);

setupFocusTrap('imageModal', closeImageModal, [
    'imageModalPrevBtn', 'imageModalNextBtn', 'imageModalCloseBtn'
]);

// Wire up the rules modal close button
document.addEventListener('DOMContentLoaded', function () {
    const closeBtn = document.getElementById('rulesModalCloseBtn');
    if (closeBtn) {
        closeBtn.addEventListener('click', closeRulesModal);
    }

    const imageModal = document.getElementById('imageModal');
    if (imageModal) {
        imageModal.addEventListener('click', function (event) {
            if (event.target === imageModal) {
                closeImageModal();
            }
        });
    }

    const imageModalCloseBtn = document.getElementById('imageModalCloseBtn');
    if (imageModalCloseBtn) {
        imageModalCloseBtn.addEventListener('click', closeImageModal);
    }

    const imageModalPrevBtn = document.getElementById('imageModalPrevBtn');
    if (imageModalPrevBtn) {
        imageModalPrevBtn.addEventListener('click', function () {
            navigateImageModal(-1);
        });
    }

    const imageModalNextBtn = document.getElementById('imageModalNextBtn');
    if (imageModalNextBtn) {
        imageModalNextBtn.addEventListener('click', function () {
            navigateImageModal(1);
        });
    }

    document.addEventListener('keydown', function (event) {
        const imageModal = document.getElementById('imageModal');
        if (!imageModal || imageModal.style.display === 'none') {
            return;
        }

        if (event.key === 'ArrowLeft') {
            event.preventDefault();
            navigateImageModal(-1);
        } else if (event.key === 'ArrowRight') {
            event.preventDefault();
            navigateImageModal(1);
        }
    });
});

// ==================== Image Modal ====================

let _imageModalTrigger = null;
let _imageModalHintPair = null;

function _applyImageModalOrientationClass(modal, imageEl) {
    const cardEl = modal ? modal.querySelector('.image-modal-card') : null;
    if (!cardEl || !imageEl) {
        return;
    }

    cardEl.classList.remove('is-portrait', 'is-landscape');
    if (imageEl.naturalHeight > imageEl.naturalWidth) {
        cardEl.classList.add('is-portrait');
        return;
    }
    cardEl.classList.add('is-landscape');
}

function _setImageModalContent(entry) {
    const modal = document.getElementById('imageModal');
    const imageEl = document.getElementById('imageModalImage');
    const captionEl = document.getElementById('imageModalCaption');

    if (!modal || !imageEl || !entry) {
        return;
    }

    imageEl.src = entry.url;
    imageEl.alt = entry.alt;
    imageEl.onload = function () {
        _applyImageModalOrientationClass(modal, imageEl);
    };
    if (imageEl.complete && imageEl.naturalWidth > 0 && imageEl.naturalHeight > 0) {
        _applyImageModalOrientationClass(modal, imageEl);
    }

    if (captionEl) {
        captionEl.textContent = entry.alt;
    }
}

function _getHintPairFromTrigger(triggerEl) {
    if (!triggerEl) {
        return null;
    }

    const isHintImage = triggerEl.id === 'image1' || triggerEl.id === 'image2';
    if (!isHintImage) {
        return null;
    }

    const image1 = document.getElementById('image1');
    const image2 = document.getElementById('image2');
    if (!image1 || !image2 || !image1.src || !image2.src) {
        return null;
    }

    const items = [
        { url: image1.src, alt: image1.alt || 'Destination image 1', trigger: image1 },
        { url: image2.src, alt: image2.alt || 'Destination image 2', trigger: image2 }
    ];

    const currentIndex = triggerEl.id === 'image2' ? 1 : 0;
    return { items, index: currentIndex };
}

function _updateImageModalNavigation() {
    const prevBtn = document.getElementById('imageModalPrevBtn');
    const nextBtn = document.getElementById('imageModalNextBtn');
    const hasPair = Boolean(_imageModalHintPair && Array.isArray(_imageModalHintPair.items) && _imageModalHintPair.items.length > 1);

    [prevBtn, nextBtn].forEach(btn => {
        if (!btn) {
            return;
        }
        btn.classList.toggle('hidden', !hasPair);
        btn.disabled = !hasPair;
    });
}

function navigateImageModal(step) {
    if (!_imageModalHintPair || !_imageModalHintPair.items.length) {
        return;
    }

    const total = _imageModalHintPair.items.length;
    const nextIndex = (_imageModalHintPair.index + step + total) % total;
    _imageModalHintPair.index = nextIndex;

    const nextEntry = _imageModalHintPair.items[nextIndex];
    _setImageModalContent(nextEntry);
    _imageModalTrigger = nextEntry.trigger;
}

function openImageModal(imageUrl, altText) {
    const modal = document.getElementById('imageModal');
    const closeBtn = document.getElementById('imageModalCloseBtn');
    const trigger = document.activeElement;

    if (!modal) {
        return;
    }

    _imageModalTrigger = trigger;
    _imageModalHintPair = _getHintPairFromTrigger(trigger);
    _updateImageModalNavigation();

    if (_imageModalHintPair) {
        _setImageModalContent(_imageModalHintPair.items[_imageModalHintPair.index]);
    } else {
        _setImageModalContent({ url: imageUrl, alt: altText, trigger });
    }

    modal.style.display = 'flex';
    if (closeBtn) {
        closeBtn.focus();
    }
}

function closeImageModal() {
    const modal = document.getElementById('imageModal');
    const imageEl = document.getElementById('imageModalImage');
    const cardEl = modal ? modal.querySelector('.image-modal-card') : null;

    if (modal) {
        modal.style.display = 'none';
    }
    if (imageEl) {
        imageEl.src = '';
    }
    if (cardEl) {
        cardEl.classList.remove('is-portrait', 'is-landscape');
    }

    if (_imageModalTrigger && typeof _imageModalTrigger.focus === 'function') {
        _imageModalTrigger.focus();
    }
    _imageModalHintPair = null;
    _imageModalTrigger = null;
}
