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
    wireZoomableImage(document.getElementById('image1'), images[0], 'Destination image 1', {
        group: 'quiz-hint-images',
        index: 0
    });
    wireZoomableImage(document.getElementById('image2'), images[1], 'Destination image 2', {
        group: 'quiz-hint-images',
        index: 1
    });
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

    if (remainingGuessesAnimationTimeout !== null) {
        clearTimeout(remainingGuessesAnimationTimeout);
        remainingGuessesAnimationTimeout = null;
    }

    const currentGuesses = Number(remainingGuessesEl.dataset.currentGuesses);
    remainingGuessesEl.classList.remove('remaining-guesses-evaporate-out', 'remaining-guesses-evaporate-in');
    remainingGuessesEl.textContent = `Remaining guesses: ${guesses}`;
    remainingGuessesEl.dataset.currentGuesses = String(guesses);
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
    if (Array.isArray(hintImages) && hintImages.length > 0) {
        quizState.hintImagesByDifficulty[hintDifficulty] = hintImages.slice();
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
    const images = Array.isArray(imageUrls)
        ? imageUrls.filter((url, index, all) => (
            typeof url === 'string' && url && all.indexOf(url) === index
        ))
        : [];
    const lightboxGroup = container.id
        ? `gallery-${container.id}`
        : `gallery-${variant}`;
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
        wireZoomableImage(image, url, `Additional destination image ${index + 1}`, {
            group: lightboxGroup,
            index
        });

        imageContainer.appendChild(image);
        container.appendChild(imageContainer);
    });
}

function getAllUnlockedHintImagesForResults() {
    const hintImages = [];
    const seen = new Set();

    const difficulties = Array.isArray(quizState.unlockedHintDifficulties)
        ? quizState.unlockedHintDifficulties
        : [];

    difficulties.forEach(difficulty => {
        const images = quizState.hintImagesByDifficulty[difficulty];
        if (!Array.isArray(images)) {
            return;
        }

        images.forEach(url => {
            if (typeof url !== 'string' || !url || seen.has(url)) {
                return;
            }
            seen.add(url);
            hintImages.push(url);
        });
    });

    return hintImages;
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
            showResults(true, result.points, result.answer, result.resultImages || [], {
                scorePreserved: Boolean(result.scorePreserved),
                preservedScore: Number.isFinite(Number(result.preservedScore))
                    ? Number(result.preservedScore)
                    : null
            });
        } else if (result.remainingGuesses !== undefined && result.remainingGuesses > 0) {
            await animateWrongGuess(answerInput);
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
            showResults(false, 0, result.answer, result.resultImages || [], {
                scorePreserved: Boolean(result.scorePreserved),
                preservedScore: Number.isFinite(Number(result.preservedScore))
                    ? Number(result.preservedScore)
                    : null
            });
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

function showResults(isCorrect, points, correctAnswer, resultImages = [], options = {}) {
    showRegisteredScreen('results', isCorrect, points, correctAnswer, resultImages, options);
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