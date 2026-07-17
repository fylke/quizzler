describe('Hint Complaint Modal', function () {
    var fixtureContainer;
    var originalFetch;

    beforeEach(function () {
        originalFetch = window.fetch;

        fixtureContainer = document.createElement('div');
        fixtureContainer.id = 'hintComplaintFixture';
        fixtureContainer.innerHTML =
            '<a href="#" id="hintComplaintLink">Complain about this hint</a>' +
            '<div id="hintComplaintModal" class="modal-overlay" style="display:none;">' +
                '<div class="modal-card">' +
                    '<h2 id="hintComplaintModalHeading">Hint complaint</h2>' +
                    '<p class="hint-complaint-context">Quiz ID: <strong id="hintComplaintQuizId"></strong> | Hint level: <strong id="hintComplaintHintLevel"></strong></p>' +
                    '<div class="modal-form-group">' +
                        '<input id="hintComplaintEmail" type="email" />' +
                    '</div>' +
                    '<div class="modal-form-group">' +
                        '<textarea id="hintComplaintMessage"></textarea>' +
                        '<span id="hintComplaintError" class="inline-error"></span>' +
                    '</div>' +
                    '<div class="modal-buttons">' +
                        '<button id="hintComplaintSendBtn">Send</button>' +
                        '<button id="hintComplaintCancelBtn">Cancel</button>' +
                    '</div>' +
                '</div>' +
            '</div>';
        document.body.appendChild(fixtureContainer);

        quizState.currentQuizId = 55;
        quizState.currentHint = {
            difficulty: 4,
            remainingGuesses: 2,
            viewedDifficulty: 5
        };
    });

    afterEach(function () {
        window.fetch = originalFetch;
        if (fixtureContainer && fixtureContainer.parentNode) {
            fixtureContainer.remove();
        }
    });

    it('prefills quiz id and selected hint level in the complaint form', function () {
        openHintComplaintModal();

        expect(document.getElementById('hintComplaintModal').style.display).toBe('flex');
        expect(document.getElementById('hintComplaintQuizId').textContent).toBe('55');
        expect(document.getElementById('hintComplaintHintLevel').textContent).toBe('5');
        expect(document.getElementById('hintComplaintEmail').value).toBe('');
    });

    it('sends complaint payload with quiz id and hint level', function (done) {
        window.fetch = function (_url, options) {
            var payload = JSON.parse(options.body);
            expect(payload.quizId).toBe(55);
            expect(payload.hintDifficulty).toBe(5);
            expect(payload.complainerEmail).toBe('reply@example.com');
            expect(payload.message).toBe('Hint has a factual error.');
            return Promise.resolve({
                ok: true,
                json: function () {
                    return Promise.resolve({ message: 'Complaint sent.' });
                }
            });
        };

        openHintComplaintModal();
        document.getElementById('hintComplaintEmail').value = 'reply@example.com';
        document.getElementById('hintComplaintMessage').value = 'Hint has a factual error.';

        handleHintComplaintSubmit().then(function () {
            expect(document.getElementById('hintComplaintModal').style.display).toBe('none');
            done();
        }).catch(function (err) {
            done.fail(err);
        });
    });
});
