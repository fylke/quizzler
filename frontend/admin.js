// ==================== Admin Panel ====================

let editingDestId = null;
let currentAdminQuizType = 'countries';
let currentAdminQuizTypeName = 'Countries';
let currentAdminTab = 'destinations';
let adminReviewStatus = 'unreviewed';
let adminReviewOffset = 0;
const adminReviewLimit = 20;
const adminTabs = ['destinations', 'review', 'background', 'stats'];

function getAdminApp() {
    return window.QuizzlerApp;
}

function bindAdminClick(elementId, handler) {
    const element = document.getElementById(elementId);
    if (element) element.addEventListener('click', handler);
}

function setupAdminEventBindings() {
    bindAdminClick('backToMainFromAdminBtn', hideAdminScreen);
    bindAdminClick('addDestinationBtn', () => showDestinationForm());
    bindAdminClick('addImageFieldBtn', () => addImageField(''));
    bindAdminClick('addAnswerFieldBtn', () => addAnswerField(''));
    bindAdminClick('saveDestinationBtn', saveDestination);
    bindAdminClick('cancelDestinationBtn', hideAdminForm);
    bindAdminClick('adminDeleteCancelBtn', hideDeleteDialog);
    bindAdminClick('adminDestinationsTab', () => setAdminTab('destinations'));
    bindAdminClick('adminReviewTab', () => setAdminTab('review'));
    bindAdminClick('adminBackgroundTab', () => setAdminTab('background'));

    bindAdminClick('uploadPortraitBgBtn', () => uploadBackground('portrait'));
    bindAdminClick('uploadLandscapeBgBtn', () => uploadBackground('landscape'));
    bindAdminClick('removePortraitBgBtn', () => removeBackground('portrait'));
    bindAdminClick('removeLandscapeBgBtn', () => removeBackground('landscape'));
    bindAdminClick('adminStatsTab', () => setAdminTab('stats'));
    bindAdminClick('adminStatsRefreshBtn', loadAdminStats);

    document.getElementById('adminReviewStatus')?.addEventListener('change', (event) => {
        adminReviewStatus = event.target.value;
        adminReviewOffset = 0;
        loadHintSourceReviews();
    });
    document.getElementById('adminReviewPreviousBtn')?.addEventListener('click', () => {
        adminReviewOffset = Math.max(0, adminReviewOffset - adminReviewLimit);
        loadHintSourceReviews();
    });
    document.getElementById('adminReviewNextBtn')?.addEventListener('click', () => {
        adminReviewOffset += adminReviewLimit;
        loadHintSourceReviews();
    });

    document.getElementById('adminQuizTypeSelect')?.addEventListener('change', (event) => {
        currentAdminQuizType = event.target.value;
        currentAdminQuizTypeName = event.target.selectedOptions[0]?.textContent || currentAdminQuizType;
        hideAdminForm();
        updateAdminTypeLabels();
        if (currentAdminTab === 'review') {
            adminReviewOffset = 0;
            loadHintSourceReviews();
        } else {
            loadDestinations();
        }
    });

    document.getElementById('adminDestList')?.addEventListener('click', (event) => {
        const button = event.target.closest('button[data-action]');
        if (!button) return;
        const destinationId = Number(button.dataset.destinationId);
        if (!Number.isFinite(destinationId)) return;
        if (button.dataset.action === 'edit-destination') {
            showDestinationForm(destinationId);
        } else if (button.dataset.action === 'delete-destination') {
            deleteDestination(destinationId, button.dataset.destinationName || '');
        }
    });

    document.getElementById('adminImagesContainer')?.addEventListener('click', (event) => {
        const button = event.target.closest('button[data-action="remove-image-field"]');
        if (button) removeImageField(button);
    });
    document.getElementById('adminAnswersContainer')?.addEventListener('click', (event) => {
        const button = event.target.closest('button[data-action="remove-answer-field"]');
        if (button) removeAnswerField(button);
    });

    document.getElementById('adminReviewList')?.addEventListener('click', (event) => {
        const button = event.target.closest('button[data-action="review-hint-source"]');
        if (!button) return;
        updateHintSourceReview(Number(button.dataset.sourceId), Number(button.dataset.difficulty), button.dataset.reviewed !== 'true');
    });
}

async function showAdminScreen() {
    getAdminApp().ui.showScreen('adminScreen');
    hideAdminForm();
    setAdminTab('destinations');
    await loadAdminQuizTypes();
    await loadDestinations();
}

function hideAdminScreen() {
    getAdminApp().ui.showStatusScreen();
}

function showAdminError(message) {
    const el = document.getElementById('adminError');
    el.textContent = message;
    el.style.display = 'block';
    setTimeout(() => { el.style.display = 'none'; }, 5000);
}

function showAdminSuccess(message) {
    const el = document.getElementById('adminSuccess');
    el.textContent = message;
    el.style.display = 'block';
    setTimeout(() => { el.style.display = 'none'; }, 3000);
}

function adminQuestionsUrl(sourceId) {
    const apiBase = getAdminApp().api.baseUrl;
    const baseUrl = `${apiBase}/api/admin/quiz-types/${encodeURIComponent(currentAdminQuizType)}/questions`;
    return sourceId ? `${baseUrl}/${sourceId}` : baseUrl;
}

function adminHintSourcesUrl(sourceId, difficulty) {
    const apiBase = getAdminApp().api.baseUrl;
    const baseUrl = `${apiBase}/api/admin/quiz-types/${encodeURIComponent(currentAdminQuizType)}/hint-sources`;
    return sourceId ? `${baseUrl}/${sourceId}/${difficulty}` : baseUrl;
}

function adminBackgroundUrl(orientation) {
    const apiBase = getAdminApp().api.baseUrl;
    const baseUrl = `${apiBase}/api/admin/settings/background`;
    return orientation ? `${baseUrl}/${orientation}` : baseUrl;
}

function setAdminTab(tab) {
    currentAdminTab = adminTabs.includes(tab) ? tab : 'destinations';
    const isDestinations = currentAdminTab === 'destinations';
    const isReview = currentAdminTab === 'review';
    const isBackground = currentAdminTab === 'background';
    const isStats = currentAdminTab === 'stats';

    if (!isDestinations) hideAdminForm();

    document.getElementById('adminDestinationsTab')?.classList.toggle('active', isDestinations);
    document.getElementById('adminReviewTab')?.classList.toggle('active', isReview);
    document.getElementById('adminBackgroundTab')?.classList.toggle('active', isBackground);
    document.getElementById('adminStatsTab')?.classList.toggle('active', isStats);

    document.getElementById('adminDestinationsTab')?.setAttribute('aria-selected', String(isDestinations));
    document.getElementById('adminReviewTab')?.setAttribute('aria-selected', String(isReview));
    document.getElementById('adminBackgroundTab')?.setAttribute('aria-selected', String(isBackground));
    document.getElementById('adminStatsTab')?.setAttribute('aria-selected', String(isStats));

    const destCount = document.getElementById('adminDestCount');
    if (destCount) destCount.style.display = isDestinations ? '' : 'none';
    const adminActions = document.querySelector('.admin-actions');
    if (adminActions) adminActions.style.display = isDestinations ? '' : 'none';
    const destList = document.getElementById('adminDestList');
    if (destList) destList.style.display = isDestinations ? '' : 'none';
    const emptyState = document.getElementById('adminEmptyState');
    if (emptyState) emptyState.style.display = isDestinations ? '' : 'none';

    const reviewPanel = document.getElementById('adminReviewPanel');
    if (reviewPanel) reviewPanel.style.display = isReview ? 'block' : 'none';
    const bgPanel = document.getElementById('adminBackgroundPanel');
    if (bgPanel) bgPanel.style.display = isBackground ? 'block' : 'none';
    const statsPanel = document.getElementById('adminStatsPanel');
    if (statsPanel) statsPanel.style.display = isStats ? 'block' : 'none';

    if (isReview) loadHintSourceReviews();
    if (isBackground) loadBackgroundSettings();
    if (isStats) loadAdminStats();
}

async function loadAdminStats() {
    const grid = document.getElementById('adminStatsGrid');
    if (!grid) return;
    grid.innerHTML = '<p class="admin-stats-loading">Loading stats...</p>';
    try {
        const response = await fetch(`${getAdminApp().api.baseUrl}/api/admin/stats`);
        if (!response.ok) {
            const err = await response.json();
            showAdminError(err.error || 'Failed to load stats');
            return;
        }
        const stats = await response.json();
        const cards = [
            ['Registered users', stats.registeredUsers],
            ['Guest sessions', stats.guestSessions],
            ['Quizzes started', stats.quizzesStarted],
            ['Quizzes completed', stats.quizzesCompleted],
            ['Quizzes ongoing', stats.quizzesOngoing],
            ['Total score', stats.cumulativeScore],
            ['Average score', stats.averageScore],
            ['Best score', stats.bestScore],
            ['Accuracy', `${stats.accuracyRate}%`],
        ];
        grid.innerHTML = cards.map(([label, value]) => `
            <article class="admin-stat-card">
                <span class="admin-stat-label">${escapeHtml(label)}</span>
                <strong class="admin-stat-value">${escapeHtml(String(value))}</strong>
            </article>
        `).join('');
    } catch (error) {
        console.error('Error loading admin stats:', error);
        grid.innerHTML = '';
        showAdminError('Could not connect to server');
    }
}

function updateAdminTypeLabels() {
    const isCountries = currentAdminQuizType === 'countries';
    document.getElementById('addDestinationBtn').textContent = isCountries
        ? 'Add New Destination'
        : `Add ${currentAdminQuizTypeName} Question`;
    document.getElementById('adminEmptyState').textContent = isCountries
        ? 'The quiz database is empty. Add a destination to get started.'
        : `No ${currentAdminQuizTypeName.toLowerCase()} questions are available.`;
    document.getElementById('adminDestName').placeholder = isCountries
        ? 'Destination name'
        : 'Question answer name';
}

async function loadAdminQuizTypes() {
    const select = document.getElementById('adminQuizTypeSelect');
    if (!select) return;
    try {
        const response = await fetch(`${getAdminApp().api.baseUrl}/api/quiz-types`);
        if (!response.ok) return;
        const quizTypes = await response.json();
        select.innerHTML = quizTypes.map(type =>
            `<option value="${escapeAttr(type.identifier)}">${escapeHtml(type.displayName)}</option>`
        ).join('');
        if (!quizTypes.some(type => type.identifier === currentAdminQuizType) && quizTypes.length) {
            currentAdminQuizType = quizTypes[0].identifier;
        }
        select.value = currentAdminQuizType;
        currentAdminQuizTypeName = select.selectedOptions[0]?.textContent || currentAdminQuizType;
        updateAdminTypeLabels();
    } catch (error) {
        console.error('Error loading admin quiz types:', error);
    }
}

async function loadDestinations() {
    const listEl = document.getElementById('adminDestList');
    const countEl = document.getElementById('adminDestCount');
    const emptyEl = document.getElementById('adminEmptyState');
    try {
        const response = await fetch(adminQuestionsUrl());
        if (!response.ok) {
            const err = await response.json();
            showAdminError(err.error || 'Failed to load destinations');
            return;
        }
        const data = await response.json();
        const destinations = data.destinations || data.questions || [];
        countEl.textContent = currentAdminQuizType === 'countries'
            ? `Total destinations: ${data.count}`
            : `Total ${currentAdminQuizTypeName.toLowerCase()} questions: ${data.count}`;

        if (destinations.length === 0) {
            emptyEl.style.display = 'block';
            listEl.innerHTML = '';
            return;
        }

        emptyEl.style.display = 'none';
        listEl.innerHTML = destinations.map(dest => `
            <div class="admin-dest-item">
                <span class="admin-dest-id">#${dest.id}</span>
                <span class="admin-dest-name">${escapeHtml(dest.name)}</span>
                <div class="admin-dest-actions">
                    <button type="button" data-action="edit-destination" data-destination-id="${dest.id}" class="btn btn-secondary btn-small">Edit</button>
                    <button type="button" data-action="delete-destination" data-destination-id="${dest.id}" data-destination-name="${escapeAttr(dest.name)}" class="btn btn-danger btn-small">Delete</button>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading destinations:', error);
        showAdminError('Could not connect to server');
    }
}

async function loadHintSourceReviews() {
    const listEl = document.getElementById('adminReviewList');
    const emptyEl = document.getElementById('adminReviewEmptyState');
    const countEl = document.getElementById('adminReviewCount');
    const previousBtn = document.getElementById('adminReviewPreviousBtn');
    const nextBtn = document.getElementById('adminReviewNextBtn');
    if (!listEl) return;
    try {
        const params = new URLSearchParams({
            status: adminReviewStatus,
            offset: String(adminReviewOffset),
            limit: String(adminReviewLimit),
        });
        const response = await fetch(`${adminHintSourcesUrl()}?${params}`);
        if (!response.ok) {
            const err = await response.json();
            showAdminError(err.error || 'Failed to load hint sources');
            return;
        }
        const data = await response.json();
        countEl.textContent = `${data.count} ${adminReviewStatus} hint source${data.count === 1 ? '' : 's'}`;
        emptyEl.style.display = data.items.length ? 'none' : 'block';
        listEl.innerHTML = data.items.map(renderHintSourceReview).join('');
        previousBtn.disabled = adminReviewOffset === 0;
        nextBtn.disabled = !data.has_more;
        document.getElementById('adminReviewPage').textContent = data.count
            ? `Page ${Math.floor(adminReviewOffset / adminReviewLimit) + 1}`
            : '';
    } catch (error) {
        console.error('Error loading hint sources:', error);
        showAdminError('Could not connect to server');
    }
}

function renderHintSourceReview(item) {
    const source = /^https?:\/\//i.test(item.source)
        ? `<a href="${escapeAttr(item.source)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.source)}</a>`
        : escapeHtml(item.source);
    const actionLabel = item.reviewed ? 'Undo review' : 'Mark reviewed';
    return `
        <article class="admin-review-item">
            <div class="admin-review-item-header">
                <strong>${escapeHtml(item.name)}</strong>
                <span class="admin-dest-id">Hint ${item.hint_difficulty}</span>
            </div>
            <p class="admin-review-hint">${escapeHtml(item.hint)}</p>
            <p class="admin-review-source"><strong>Source:</strong> ${source}</p>
            ${item.reviewed_at ? `<p class="admin-review-meta">Reviewed by ${escapeHtml(item.reviewed_by || 'admin')} on ${escapeHtml(new Date(item.reviewed_at).toLocaleString())}</p>` : ''}
            <button type="button" class="btn btn-secondary btn-small" data-action="review-hint-source" data-source-id="${item.source_id}" data-difficulty="${item.hint_difficulty}" data-reviewed="${item.reviewed}">${actionLabel}</button>
        </article>
    `;
}

async function updateHintSourceReview(sourceId, difficulty, reviewed) {
    const app = getAdminApp();
    const headers = { 'Content-Type': 'application/json' };
    if (app.state.csrfToken) headers['X-CSRF-Token'] = app.state.csrfToken;
    try {
        const response = await fetch(adminHintSourcesUrl(sourceId, difficulty), {
            method: 'PATCH',
            headers,
            body: JSON.stringify({ reviewed }),
        });
        if (!response.ok) {
            const err = await response.json();
            showAdminError(err.error || 'Failed to update review status');
            return;
        }
        showAdminSuccess(reviewed ? 'Hint source marked reviewed' : 'Hint source returned to review');
        loadHintSourceReviews();
    } catch (error) {
        console.error('Error updating hint source review:', error);
        showAdminError('Could not connect to server');
    }
}

async function loadBackgroundSettings() {
    try {
        const response = await fetch(`${getAdminApp().api.baseUrl}/api/settings/background`);
        if (!response.ok) {
            const err = await response.json();
            showAdminError(err.error || 'Failed to load background settings');
            return;
        }
        const data = await response.json();
        updateBackgroundUI('portrait', data.portrait);
        updateBackgroundUI('landscape', data.landscape);
        if (typeof applyAppBackground === 'function') {
            applyAppBackground(data);
        } else if (getAdminApp()?.ui?.applyAppBackground) {
            getAdminApp().ui.applyAppBackground(data);
        }
    } catch (error) {
        console.error('Error loading background settings:', error);
        showAdminError('Could not connect to server');
    }
}

function updateBackgroundUI(orientation, imageUrl) {
    const isPortrait = orientation === 'portrait';
    const emptyEl = document.getElementById(isPortrait ? 'portraitBgEmptyText' : 'landscapeBgEmptyText');
    const wrapperEl = document.getElementById(isPortrait ? 'portraitBgPreviewWrapper' : 'landscapeBgPreviewWrapper');
    const imgEl = document.getElementById(isPortrait ? 'portraitBgPreviewImg' : 'landscapeBgPreviewImg');
    const filenameEl = document.getElementById(isPortrait ? 'portraitBgFilename' : 'landscapeBgFilename');
    const removeBtn = document.getElementById(isPortrait ? 'removePortraitBgBtn' : 'removeLandscapeBgBtn');
    const inputEl = document.getElementById(isPortrait ? 'adminPortraitBgInput' : 'adminLandscapeBgInput');

    if (inputEl) inputEl.value = '';

    if (imageUrl) {
        if (emptyEl) emptyEl.style.display = 'none';
        if (wrapperEl) wrapperEl.style.display = 'flex';
        if (imgEl) imgEl.src = imageUrl;
        if (filenameEl) filenameEl.textContent = imageUrl.split('/').pop() || imageUrl;
        if (removeBtn) removeBtn.style.display = 'inline-block';
    } else {
        if (emptyEl) emptyEl.style.display = 'block';
        if (wrapperEl) wrapperEl.style.display = 'none';
        if (imgEl) imgEl.removeAttribute('src');
        if (filenameEl) filenameEl.textContent = '';
        if (removeBtn) removeBtn.style.display = 'none';
    }
}

async function uploadBackground(orientation) {
    const inputEl = document.getElementById(orientation === 'portrait' ? 'adminPortraitBgInput' : 'adminLandscapeBgInput');
    const file = inputEl?.files?.[0];
    if (!file) {
        showAdminError(`Please select an image file for ${orientation} background`);
        return;
    }

    const app = getAdminApp();
    const formData = new FormData();
    formData.append(orientation, file);

    const headers = {};
    if (app.state.csrfToken) {
        headers['X-CSRF-Token'] = app.state.csrfToken;
    }

    try {
        const response = await fetch(`${app.api.baseUrl}/api/admin/settings/background`, {
            method: 'POST',
            headers,
            body: formData
        });

        if (!response.ok) {
            const err = await response.json();
            showAdminError(err.error || `Failed to upload ${orientation} background`);
            return;
        }

        const data = await response.json();
        showAdminSuccess(`${orientation.charAt(0).toUpperCase() + orientation.slice(1)} background updated successfully`);
        updateBackgroundUI('portrait', data.portrait);
        updateBackgroundUI('landscape', data.landscape);
        if (typeof applyAppBackground === 'function') {
            applyAppBackground(data);
        } else if (getAdminApp()?.ui?.applyAppBackground) {
            getAdminApp().ui.applyAppBackground(data);
        }
    } catch (error) {
        console.error(`Error uploading ${orientation} background:`, error);
        showAdminError('Could not connect to server');
    }
}

async function removeBackground(orientation) {
    const app = getAdminApp();
    const headers = {};
    if (app.state.csrfToken) {
        headers['X-CSRF-Token'] = app.state.csrfToken;
    }

    try {
        const response = await fetch(`${app.api.baseUrl}/api/admin/settings/background/${orientation}`, {
            method: 'DELETE',
            headers
        });

        if (!response.ok) {
            const err = await response.json();
            showAdminError(err.error || `Failed to remove ${orientation} background`);
            return;
        }

        const data = await response.json();
        showAdminSuccess(`${orientation.charAt(0).toUpperCase() + orientation.slice(1)} background removed successfully`);
        updateBackgroundUI('portrait', data.portrait);
        updateBackgroundUI('landscape', data.landscape);
        if (typeof applyAppBackground === 'function') {
            applyAppBackground(data);
        } else if (getAdminApp()?.ui?.applyAppBackground) {
            getAdminApp().ui.applyAppBackground(data);
        }
    } catch (error) {
        console.error(`Error removing ${orientation} background:`, error);
        showAdminError('Could not connect to server');
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function showDestinationForm(id) {
    editingDestId = id || null;
    const formTitle = document.getElementById('adminFormTitle');
    const formEl = document.getElementById('adminForm');

    // Clear form fields
    document.getElementById('adminDestName').value = '';
    for (let i = 1; i <= 5; i++) {
        document.getElementById(`adminHint${i}`).value = '';
        const sourceInput = document.getElementById(`adminHintSource${i}`);
        if (sourceInput) sourceInput.value = '';
    }
    document.getElementById('adminImagesContainer').innerHTML = '';
    document.getElementById('adminAnswersContainer').innerHTML = '';

    if (editingDestId) {
        formTitle.textContent = currentAdminQuizType === 'countries'
            ? 'Edit Destination'
            : `Edit ${currentAdminQuizTypeName} Question`;
        try {
            const response = await fetch(adminQuestionsUrl(editingDestId));
            if (!response.ok) {
                const err = await response.json();
                showAdminError(err.error || 'Failed to load destination');
                return;
            }
            const dest = await response.json();
            document.getElementById('adminDestName').value = dest.name;
            for (let i = 0; i < 5; i++) {
                document.getElementById(`adminHint${i + 1}`).value = dest.hints[i] || '';
                const sourceInput = document.getElementById(`adminHintSource${i + 1}`);
                if (sourceInput) sourceInput.value = dest.hint_sources?.[i] || '';
            }
            (dest.images || []).forEach(url => addImageField(url));
            if (!dest.images || dest.images.length === 0) {
                addImageField('');
                addImageField('');
            }
            dest.correct_answers.forEach(ans => addAnswerField(ans));
        } catch (error) {
            console.error('Error loading destination:', error);
            showAdminError('Could not connect to server');
            return;
        }
    } else {
        formTitle.textContent = currentAdminQuizType === 'countries'
            ? 'Add New Destination'
            : `Add ${currentAdminQuizTypeName} Question`;
        // Start with 2 image fields and 1 answer field
        addImageField('');
        addImageField('');
        addAnswerField('');
    }

    // Show form, hide list
    formEl.style.display = 'block';
    document.getElementById('adminDestList').style.display = 'none';
    document.querySelector('.admin-actions').style.display = 'none';
    document.getElementById('adminDestCount').style.display = 'none';
    document.getElementById('adminEmptyState').style.display = 'none';
}

function hideAdminForm() {
    const form = document.getElementById('adminForm');
    if (form) form.style.display = 'none';
    const destList = document.getElementById('adminDestList');
    if (destList) destList.style.display = '';
    const actions = document.querySelector('.admin-actions');
    if (actions) actions.style.display = '';
    const destCount = document.getElementById('adminDestCount');
    if (destCount) destCount.style.display = '';
    editingDestId = null;
}

async function saveDestination() {
    const app = getAdminApp();
    const rules = app.state.validationRules;
    const name = document.getElementById('adminDestName').value.trim();
    const hints = [];
    const hint_sources = [];
    for (let i = 1; i <= 5; i++) {
        hints.push(document.getElementById(`adminHint${i}`).value.trim());
        const sourceInput = document.getElementById(`adminHintSource${i}`);
        hint_sources.push(sourceInput ? sourceInput.value.trim() || null : null);
    }
    const imageInputs = document.querySelectorAll('#adminImagesContainer input');
    const imageFiles = Array.from(imageInputs).flatMap(input => Array.from(input.files || []));
    const answerInputs = document.querySelectorAll('#adminAnswersContainer input');
    const correct_answers = Array.from(answerInputs).map(input => input.value.trim()).filter(v => v);

    // Client-side validation
    if (!name) {
        showAdminError('Name is required');
        return;
    }
    if (name.length > rules.destination.nameMaxLength) {
        showAdminError(`Name must be ${rules.destination.nameMaxLength} characters or less`);
        return;
    }
    for (let i = 0; i < rules.destination.hintCount; i++) {
        if (!hints[i]) {
            showAdminError(`Hint ${i + 1} is required`);
            return;
        }
        if (hints[i].length > rules.destination.hintMaxLength) {
            showAdminError(`Hint ${i + 1} must be ${rules.destination.hintMaxLength} characters or less`);
            return;
        }
    }
    if (imageFiles.length < rules.destination.imagesMinCount) {
        showAdminError(`At least ${rules.destination.imagesMinCount} images are required`);
        return;
    }
    if (imageFiles.length > rules.destination.imagesMaxCount) {
        showAdminError(`No more than ${rules.destination.imagesMaxCount} images are allowed`);
        return;
    }
    if (correct_answers.length < rules.destination.answersMinCount || correct_answers.length > rules.destination.answersMaxCount) {
        showAdminError(`Between ${rules.destination.answersMinCount} and ${rules.destination.answersMaxCount} correct answers are required`);
        return;
    }

    const payload = { name, hints, hint_sources, correct_answers };
    const headers = { 'Content-Type': 'application/json' };
    if (app.state.csrfToken) {
        headers['X-CSRF-Token'] = app.state.csrfToken;
    }

    try {
        let response;
        let savedQuestionId = editingDestId;
        if (editingDestId) {
            response = await fetch(adminQuestionsUrl(editingDestId), {
                method: 'PUT',
                headers,
                body: JSON.stringify(payload)
            });
        } else {
            response = await fetch(adminQuestionsUrl(), {
                method: 'POST',
                headers,
                body: JSON.stringify(payload)
            });
        }

        if (!response.ok) {
            const err = await response.json();
            if (err.details) {
                showAdminError(err.details.join(', '));
            } else {
                showAdminError(err.error || 'Failed to save destination');
            }
            return;
        }

        if (!savedQuestionId) {
            savedQuestionId = (await response.clone().json()).id;
        }
        const imageData = new FormData();
        imageFiles.forEach(file => imageData.append('images', file));
        const uploadHeaders = {};
        if (app.state.csrfToken) {
            uploadHeaders['X-CSRF-Token'] = app.state.csrfToken;
        }
        const imageResponse = await fetch(`${adminQuestionsUrl(savedQuestionId)}/images`, {
            method: 'POST',
            headers: uploadHeaders,
            body: imageData
        });
        if (!imageResponse.ok) {
            const err = await imageResponse.json();
            showAdminError(err.error || 'Failed to upload images');
            return;
        }

        const itemName = currentAdminQuizType === 'countries' ? 'Destination' : 'Question';
        showAdminSuccess(editingDestId ? `${itemName} updated successfully` : `${itemName} created successfully`);
        hideAdminForm();
        loadDestinations();
    } catch (error) {
        console.error('Error saving destination:', error);
        showAdminError('Could not connect to server');
    }
}

function deleteDestination(id, name) {
    const app = getAdminApp();
    const dialog = document.getElementById('adminDeleteDialog');
    document.getElementById('adminDeleteName').textContent = name;
    dialog.style.display = 'flex';

    const confirmBtn = document.getElementById('adminDeleteConfirmBtn');
    // Remove old listener by replacing the node
    const newBtn = confirmBtn.cloneNode(true);
    confirmBtn.parentNode.replaceChild(newBtn, confirmBtn);
    newBtn.addEventListener('click', async () => {
        const headers = {};
        if (app.state.csrfToken) {
            headers['X-CSRF-Token'] = app.state.csrfToken;
        }
        try {
            const response = await fetch(adminQuestionsUrl(id), {
                method: 'DELETE',
                headers
            });
            if (!response.ok) {
                const err = await response.json();
                showAdminError(err.error || 'Failed to delete destination');
            } else {
                showAdminSuccess(currentAdminQuizType === 'countries'
                    ? 'Destination deleted successfully'
                    : 'Question deleted successfully');
                loadDestinations();
            }
        } catch (error) {
            console.error('Error deleting destination:', error);
            showAdminError('Could not connect to server');
        }
        hideDeleteDialog();
    });
}

function hideDeleteDialog() {
    document.getElementById('adminDeleteDialog').style.display = 'none';
}

function addImageField(value) {
    const container = document.getElementById('adminImagesContainer');
    const row = document.createElement('div');
    row.className = 'admin-dynamic-field-row';
    row.innerHTML = `
        <input type="file" accept="image/*"${value ? ` data-existing-image="${escapeAttr(value)}"` : ''}>
        <button type="button" data-action="remove-image-field" class="btn btn-danger btn-small">✕</button>
    `;
    container.appendChild(row);
}

function removeImageField(btn) {
    btn.parentElement.remove();
}

function addAnswerField(value) {
    const container = document.getElementById('adminAnswersContainer');
    const row = document.createElement('div');
    row.className = 'admin-dynamic-field-row';
    row.innerHTML = `
        <input type="text" value="${escapeAttr(value || '')}" maxlength="128" placeholder="Correct answer">
        <button type="button" data-action="remove-answer-field" class="btn btn-danger btn-small">✕</button>
    `;
    container.appendChild(row);
}

function removeAnswerField(btn) {
    btn.parentElement.remove();
}

function escapeAttr(str) {
    return str.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

document.addEventListener('DOMContentLoaded', () => {
    setupAdminEventBindings();
});
