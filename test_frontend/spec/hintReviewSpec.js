describe('Hint Review', function () {
    var fixtureContainer;
    var originalFetch;

    beforeEach(function () {
        originalFetch = window.fetch;
        fixtureContainer = document.createElement('div');
        fixtureContainer.id = 'hintReviewFixture';
        fixtureContainer.innerHTML =
            '<div id="quizScreen" class="screen">' +
                '<div class="progress-info">' +
                    '<span id="currentHint">Hardest difficulty (15p)</span>' +
                '</div>' +
                '<div class="hint-section"><h2 id="hint"></h2></div>' +
                '<div class="hint-meta">' +
                    '<span id="hintProgress"></span>' +
                    '<span id="hintPoints"></span>' +
                '</div>' +
                '<div class="hint-review hidden" id="hintReviewSection">' +
                    '<span class="hint-review-label">Review previous hints</span>' +
                    '<div id="hintHistoryButtons" class="hint-history-buttons"></div>' +
                '</div>' +
                '<input id="answerInput" />' +
                '<div class="button-group">' +
                    '<div class="next-hint-wrap">' +
                        '<span id="nextHintCostPreview" class="next-hint-cost-preview"></span>' +
                        '<button onclick="skipHint()" class="btn btn-secondary">Next Hint</button>' +
                    '</div>' +
                '</div>' +
                '<div id="progressFill"></div>' +
                '<img id="image1" />' +
                '<img id="image2" />' +
            '</div>';
        document.body.appendChild(fixtureContainer);

        resetHintReviewState();
    });

    afterEach(function () {
        window.fetch = originalFetch;
        resetHintReviewState();
        if (fixtureContainer && fixtureContainer.parentNode) {
            fixtureContainer.remove();
        }
    });

    it('shows review controls once multiple hints are unlocked', function () {
        updateHintDisplay('Harder hint', 5, 5);

        var reviewSection = document.getElementById('hintReviewSection');
        expect(reviewSection.classList.contains('hidden')).toBe(true);

        updateHintDisplay('Easier hint', 4, 4);

        expect(reviewSection.classList.contains('hidden')).toBe(false);
        expect(document.querySelectorAll('#hintHistoryButtons .hint-history-btn').length).toBe(2);
    });

    it('allows viewing a previous hint', function () {
        updateHintDisplay('Harder hint', 5, 5);
        updateHintDisplay('Easier hint', 4, 4);

        var buttons = document.querySelectorAll('#hintHistoryButtons .hint-history-btn');
        expect(buttons.length).toBe(2);

        buttons[0].click();

        expect(document.getElementById('hint').textContent).toBe('Harder hint');
        expect(document.getElementById('hintProgress').textContent).toBe('');
        expect(document.getElementById('hintPoints').textContent).toBe('');
    });

    it('renders hint history buttons as ordinal labels', function () {
        updateHintDisplay('Hardest hint', 5, 5);
        updateHintDisplay('Hard hint', 4, 4);
        updateHintDisplay('Medium hint', 3, 3);

        var labels = Array.from(document.querySelectorAll('#hintHistoryButtons .hint-history-btn')).map(function (button) {
            return button.textContent;
        });

        expect(labels).toEqual(['First', 'Second', 'Third']);
    });

    it('updates quiz images when skipping to a new hint', function (done) {
        displayQuiz({
            id: 12,
            hint: 'Starting hint',
            hintDifficulty: 5,
            remainingGuesses: 3,
            images: ['/media/countries/12/5a.jpg', '/media/countries/12/5b.jpg']
        });

        window.fetch = function (url) {
            if (url.indexOf('/api/hint') !== -1) {
                return Promise.resolve({
                    ok: true,
                    json: function () {
                        return Promise.resolve({
                            hint: 'Easier hint',
                            hintDifficulty: 4,
                            remainingGuesses: 3,
                            images: ['/media/countries/12/4a.jpg', '/media/countries/12/4b.jpg']
                        });
                    }
                });
            }
            return Promise.resolve({ ok: true, json: function () { return Promise.resolve({}); } });
        };

        fetchHint().then(function () {
            expect(document.getElementById('image1').src).toContain('/media/countries/12/4a.jpg');
            expect(document.getElementById('image2').src).toContain('/media/countries/12/4b.jpg');
            done();
        }).catch(function (error) {
            done.fail(error);
        });
    });

    it('updates the top hint counter when moving to easier hints', function () {
        updateHintDisplay('Hardest hint', 5, 3);
        expect(document.getElementById('currentHint').textContent).toBe('Hardest difficulty (15p)');

        updateHintDisplay('Second hint', 4, 3);
        expect(document.getElementById('currentHint').textContent).toBe('Hard difficulty (12p)');

        updateHintDisplay('Third hint', 3, 2);
        expect(document.getElementById('currentHint').textContent).toBe('Medium difficulty (6p)');
    });

    it('shows point loss preview for next hint based on current state', function () {
        updateHintDisplay('Hardest hint', 5, 3);
        expect(document.getElementById('nextHintCostPreview').textContent).toBe('(-3p)');

        updateHintDisplay('Easiest hint', 1, 2);
        expect(document.getElementById('nextHintCostPreview').textContent).toBe('(-0p)');
    });

    it('animates top points when a wrong answer lowers points', function (done) {
        updateHintDisplay('Hardest hint', 5, 3);
        updateHintDisplay('Hardest hint', 5, 2, { animatePointsEvaporation: true });

        expect(document.getElementById('currentHint').classList.contains('points-evaporate-out')).toBe(true);

        setTimeout(function () {
            expect(document.getElementById('currentHint').textContent).toBe('Hardest difficulty (10p)');
            done();
        }, 320);
    });
});
