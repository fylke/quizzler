let friendGameState = {
    token: null,
    position: null,
    currentQuestion: null,
    pollingId: null
};

function friendGameElement(id) {
    return document.getElementById(id);
}

function renderFriendLeaderboard(rows) {
    const list = friendGameElement('friendGameLeaderboardList');
    if (!list) return;
    list.replaceChildren();
    (Array.isArray(rows) ? rows : []).forEach(row => {
        const item = document.createElement('li');
        const name = document.createElement('span');
        const score = document.createElement('span');
        name.textContent = `${row.displayName}${row.completed ? ' (finished)' : ''}`;
        score.textContent = `${row.score} points`;
        item.append(name, score);
        list.appendChild(item);
    });
}

function setFriendGameStatus(message) {
    const status = friendGameElement('friendGameStatus');
    if (status) status.textContent = message || '';
}

function hideFriendGamePanels() {
    ['friendGameCreateForm', 'friendGameJoinForm', 'friendGameLobby', 'friendGamePlay']
        .forEach(id => friendGameElement(id)?.classList.add('hidden'));
}

function showFriendGamePanel(id) {
    friendGameElement(id)?.classList.remove('hidden');
}

async function ensureFriendGameCsrf() {
    if (appState.csrfToken) return appState.csrfToken;
    const response = await fetch(`${API_BASE}/api/friend-games/csrf`);
    if (!response.ok) throw new Error('Unable to prepare friend game.');
    const data = await response.json();
    appState.csrfToken = data.csrfToken || null;
    return appState.csrfToken;
}

async function friendGameRequest(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (options.method && options.method !== 'GET') {
        headers['Content-Type'] = 'application/json';
        headers['X-CSRF-Token'] = await ensureFriendGameCsrf();
    }
    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    let data = {};
    try { data = await response.json(); } catch (error) { /* keep empty payload */ }
    if (!response.ok) throw new Error(data.error || 'Friend game request failed.');
    return data;
}

function renderFriendQuestion(state) {
    const question = state.question || {};
    friendGameState.position = Number.isFinite(Number(question.position)) ? Number(question.position) : null;
    friendGameState.currentQuestion = question;
    const complete = friendGameState.position === Number(question.questionCount);
    friendGameElement('friendGameProgress').textContent = complete
        ? 'You finished all questions.'
        : `Question ${friendGameState.position + 1} of ${question.questionCount}`;
    friendGameElement('friendGameHint').textContent = question.hint || '';
    friendGameElement('friendGameGuesses').textContent = complete
        ? ''
        : `Remaining guesses: ${question.remainingGuesses}`;
    const images = Array.isArray(question.images) ? question.images : [];
    ['friendGameImage1', 'friendGameImage2'].forEach((id, index) => {
        const image = friendGameElement(id);
        image.src = images[index] || '';
        image.classList.toggle('hidden', !images[index]);
    });
    friendGameElement('friendGameAnswer').value = '';
    friendGameElement('friendGameAnswer').disabled = complete;
    friendGameElement('friendGameSubmitBtn').disabled = complete;
    friendGameElement('friendGameHintBtn').disabled = complete;
}

function renderFriendState(state) {
    hideFriendGamePanels();
    showFriendGamePanel('friendGamePlay');
    renderFriendQuestion(state);
    renderFriendLeaderboard(state.leaderboard);
    const invite = friendGameElement('friendGameInvite');
    if (invite && friendGameState.token) invite.textContent = `${window.location.origin}/friend/${friendGameState.token}`;
}

async function refreshFriendGameState() {
    if (!friendGameState.token) return;
    try {
        const state = await friendGameRequest(`/api/friend-games/${encodeURIComponent(friendGameState.token)}/state`);
        renderFriendState(state);
    } catch (error) {
        setFriendGameStatus(error.message);
    }
}

function startFriendPolling() {
    if (friendGameState.pollingId) clearInterval(friendGameState.pollingId);
    friendGameState.pollingId = setInterval(async () => {
        if (friendGameState.token) {
            try {
                const data = await friendGameRequest(`/api/friend-games/${encodeURIComponent(friendGameState.token)}/results`);
                renderFriendLeaderboard(data.leaderboard);
            } catch (error) {
                clearInterval(friendGameState.pollingId);
                friendGameState.pollingId = null;
            }
        }
    }, 5000);
}

const friendGameScreenController = {
    showCreate() {
        friendGameState.token = null;
        showScreen('friendGameScreen');
        hideFriendGamePanels();
        showFriendGamePanel('friendGameCreateForm');
        friendGameElement('friendGameLeaderboardList').replaceChildren();
        setFriendGameStatus('Choose the number of questions and invite your friends.');
    },

    async start(token) {
        friendGameState.token = token;
        showScreen('friendGameScreen');
        hideFriendGamePanels();
        setFriendGameStatus('Loading friend game...');
        try {
            await friendGameRequest(`/api/friend-games/${encodeURIComponent(token)}`);
            const state = await friendGameRequest(`/api/friend-games/${encodeURIComponent(token)}/state`);
            renderFriendState(state);
        } catch (stateError) {
            if (stateError.message === 'Join this friend game first') {
                showFriendGamePanel('friendGameJoinForm');
                setFriendGameStatus('Choose a display name to join this game.');
            } else {
                showNotification(stateError.message);
                setFriendGameStatus(stateError.message);
            }
        }
        startFriendPolling();
        return true;
    }
};

async function createFriendGame() {
    const count = Number(friendGameElement('friendGameQuestionCount').value);
    const quizIdsText = friendGameElement('friendGameQuizIds').value.trim();
    const displayName = friendGameElement('friendGameCreateName').value;
    const payload = { questionCount: count, displayName, quizType: 'countries' };
    if (quizIdsText) {
        const quizIds = quizIdsText.split(',').map(value => Number(value.trim()));
        if (quizIds.some(id => !Number.isInteger(id) || id < 1)) {
            showNotification('Quiz IDs must be positive integers separated by commas.');
            return;
        }
        payload.quizIds = quizIds;
    }
    try {
        const data = await friendGameRequest('/api/friend-games', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
        friendGameState.token = data.token;
        friendGameElement('friendGameInvite').textContent = `${window.location.origin}${data.url}`;
        hideFriendGamePanels();
        showFriendGamePanel('friendGameLobby');
        setFriendGameStatus('Game created. Share the invite link, then start playing.');
        renderFriendLeaderboard([]);
        await refreshFriendGameState();
        showFriendGamePanel('friendGameLobby');
    } catch (error) {
        showNotification(error.message);
    }
}

async function joinFriendGame() {
    try {
        const state = await friendGameRequest(`/api/friend-games/${encodeURIComponent(friendGameState.token)}/join`, {
            method: 'POST',
            body: JSON.stringify({ displayName: friendGameElement('friendGameJoinName').value })
        });
        renderFriendState(state);
    } catch (error) {
        showNotification(error.message);
    }
}

async function submitFriendGameAnswer() {
    const answer = friendGameElement('friendGameAnswer').value;
    try {
        const state = await friendGameRequest(`/api/friend-games/${encodeURIComponent(friendGameState.token)}/answer`, {
            method: 'POST',
            body: JSON.stringify({ position: friendGameState.position, answer })
        });
        setFriendGameStatus(state.correct ? `Correct! +${state.points} points.` : 'Not quite.');
        renderFriendState(state);
    } catch (error) {
        showNotification(error.message);
    }
}

async function requestFriendGameHint() {
    try {
        const state = await friendGameRequest(`/api/friend-games/${encodeURIComponent(friendGameState.token)}/hint`, { method: 'POST' });
        renderFriendState(state);
    } catch (error) {
        showNotification(error.message);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    friendGameElement('friendGameCreateForm')?.addEventListener('submit', event => {
        event.preventDefault();
        createFriendGame();
    });
    friendGameElement('friendGameJoinForm')?.addEventListener('submit', event => {
        event.preventDefault();
        joinFriendGame();
    });
    friendGameElement('friendGameSubmitBtn')?.addEventListener('click', submitFriendGameAnswer);
    friendGameElement('friendGameHintBtn')?.addEventListener('click', requestFriendGameHint);
    friendGameElement('friendGameStartBtn')?.addEventListener('click', refreshFriendGameState);
    friendGameElement('friendGameCopyBtn')?.addEventListener('click', async () => {
        try {
            await navigator.clipboard.writeText(friendGameElement('friendGameInvite').textContent);
            showNotification('Friend game link copied.', 'success');
        } catch (error) {
            showNotification('Unable to copy friend game link.');
        }
    });
});

registerScreenController('friendGame', friendGameScreenController);
