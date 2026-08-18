// ==================== Admin Panel ====================

let editingDestId = null;
let currentAdminQuizType = 'countries';
let currentAdminQuizTypeName = 'Countries';

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

    document.getElementById('adminQuizTypeSelect')?.addEventListener('change', (event) => {
        currentAdminQuizType = event.target.value;
        currentAdminQuizTypeName = event.target.selectedOptions[0]?.textContent || currentAdminQuizType;
        hideAdminForm();
        updateAdminTypeLabels();
        loadDestinations();
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
}

async function showAdminScreen() {
    getAdminApp().ui.showScreen('adminScreen');
    hideAdminForm();
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
    const baseUrl = currentAdminQuizType === 'countries'
        ? `${apiBase}/api/admin/destinations`
        : `${apiBase}/api/admin/quiz-types/${encodeURIComponent(currentAdminQuizType)}/questions`;
    return sourceId ? `${baseUrl}/${sourceId}` : baseUrl;
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
    document.getElementById('adminForm').style.display = 'none';
    document.getElementById('adminDestList').style.display = '';
    document.querySelector('.admin-actions').style.display = '';
    document.getElementById('adminDestCount').style.display = '';
    editingDestId = null;
}

async function saveDestination() {
    const app = getAdminApp();
    const rules = app.state.validationRules;
    const name = document.getElementById('adminDestName').value.trim();
    const hints = [];
    for (let i = 1; i <= 5; i++) {
        hints.push(document.getElementById(`adminHint${i}`).value.trim());
    }
    const imageInputs = document.querySelectorAll('#adminImagesContainer input');
    const images = Array.from(imageInputs).map(input => input.value.trim()).filter(v => v);
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
    if (images.length < rules.destination.imagesMinCount) {
        showAdminError(`At least ${rules.destination.imagesMinCount} image URLs are required`);
        return;
    }
    if (images.length > rules.destination.imagesMaxCount) {
        showAdminError(`No more than ${rules.destination.imagesMaxCount} image URLs are allowed`);
        return;
    }
    if (correct_answers.length < rules.destination.answersMinCount || correct_answers.length > rules.destination.answersMaxCount) {
        showAdminError(`Between ${rules.destination.answersMinCount} and ${rules.destination.answersMaxCount} correct answers are required`);
        return;
    }

    const payload = { name, hints, images, correct_answers };
    const headers = { 'Content-Type': 'application/json' };
    if (app.state.csrfToken) {
        headers['X-CSRF-Token'] = app.state.csrfToken;
    }

    try {
        let response;
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
        <input type="url" value="${escapeAttr(value || '')}" placeholder="https://example.com/image.jpg">
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
