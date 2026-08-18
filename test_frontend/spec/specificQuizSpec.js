// Feature: quiz sharing: Specific quiz by GUID behavior
describe('Specific Quiz by GUID', function () {

    // **Validates: Requirements 6.1, 6.2, 6.3, 6.4**

    var originalFetch;
    var fixtureContainer;

    beforeEach(function () {
        originalFetch = window.fetch;

        // Create fixture with the specific quiz input section
        fixtureContainer = document.createElement('div');
        fixtureContainer.id = 'specificQuizFixture';
        fixtureContainer.innerHTML =
            '<div class="quiz-actions">' +
                '<div class="specific-quiz-section">' +
                    '<div class="input-row">' +
                        '<input type="text" id="specificQuizId" placeholder="Paste quiz GUID">' +
                        '<button onclick="runSpecificQuiz()" class="btn btn-primary" id="runSpecificQuizBtn">Go</button>' +
                    '</div>' +
                '</div>' +
                '<button id="runRandomQuizBtn">Run Random Quiz</button>' +
                '<button id="adminLink" style="display:none;">Admin Panel</button>' +
                '<button id="logoutBtn">Logout</button>' +
            '</div>';
        document.body.appendChild(fixtureContainer);
    });

    afterEach(function () {
        window.fetch = originalFetch;

        if (fixtureContainer && fixtureContainer.parentNode) {
            fixtureContainer.remove();
        }

        // Clean up notifications
        var notification = document.getElementById('appNotification');
        if (notification) {
            notification.remove();
        }
    });

    describe('Requirement 6.1: Input field presence', function () {

        it('has a text input field', function () {
            var input = document.getElementById('specificQuizId');
            expect(input).not.toBeNull();
            expect(input.type).toBe('text');
            expect(input.placeholder).toBe('Paste quiz GUID');
        });

        it('does not render a separate label for specific quiz input', function () {
            var label = fixtureContainer.querySelector('label[for="specificQuizId"]');
            expect(label).toBeNull();
        });

        it('has a submit button', function () {
            var btn = document.getElementById('runSpecificQuizBtn');
            expect(btn).not.toBeNull();
            expect(btn.textContent).toContain('Go');
        });
    });

    describe('Requirement 6.3: Empty ID shows notification', function () {

        it('shows notification when quiz ID is empty', function () {
            var input = document.getElementById('specificQuizId');
            input.value = '';

            runSpecificQuiz();

            var notification = document.getElementById('appNotification');
            expect(notification).not.toBeNull();
            expect(notification.textContent).toContain('Quiz not found');
        });

        it('shows notification when quiz ID is whitespace only', function () {
            var input = document.getElementById('specificQuizId');
            input.value = '   ';

            runSpecificQuiz();

            var notification = document.getElementById('appNotification');
            expect(notification).not.toBeNull();
            expect(notification.textContent).toContain('Quiz not found');
        });

        it('shows notification when quiz GUID is malformed', function () {
            var input = document.getElementById('specificQuizId');
            input.value = 'abc';

            runSpecificQuiz();

            var notification = document.getElementById('appNotification');
            expect(notification).not.toBeNull();
            expect(notification.textContent).toContain('Quiz not found');
        });
    });

    describe('Requirement 6.4: Non-existent ID shows notification', function () {

        it('shows notification when backend returns quiz not found', function (done) {
            var input = document.getElementById('specificQuizId');
            input.value = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';

            window.fetch = function (url) {
                if (url.indexOf('/api/quiz/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa') !== -1) {
                    return Promise.resolve({
                        ok: false,
                        json: function () {
                            return Promise.resolve({ error: 'Destination not found' });
                        }
                    });
                }
                return Promise.resolve({ ok: true, json: function () { return Promise.resolve({}); } });
            };

            runSpecificQuiz();

            // Wait for async operations
            setTimeout(function () {
                var notification = document.getElementById('appNotification');
                expect(notification).not.toBeNull();
                expect(notification.textContent).toContain('Quiz not found');
                done();
            }, 100);
        });
    });

    describe('Requirement 6.2: Successful quiz load', function () {

        it('navigates to quiz screen when valid GUID returns quiz data', function (done) {
            var input = document.getElementById('specificQuizId');
            input.value = '11111111-1111-4111-8111-111111111111';

            window.fetch = function (url) {
                if (url.indexOf('/api/quiz/11111111-1111-4111-8111-111111111111') !== -1) {
                    return Promise.resolve({
                        ok: true,
                        json: function () {
                            return Promise.resolve({
                                id: 5,
                                guid: '11111111-1111-4111-8111-111111111111',
                                hint: 'A famous European capital',
                                hintDifficulty: 3,
                                remainingGuesses: 5,
                                images: ['/media/countries/5/1a.jpg', '/media/countries/5/1b.jpg']
                            });
                        }
                    });
                }
                return Promise.resolve({ ok: true, json: function () { return Promise.resolve({}); } });
            };

            runSpecificQuiz();

            // Wait for async operations
            setTimeout(function () {
                var quizScreen = document.getElementById('quizScreen');
                // Should have navigated to quiz screen (not hidden)
                expect(quizScreen.classList.contains('hidden')).toBe(false);
                done();
            }, 100);
        });
    });

    describe('Specific quiz input coexists with quiz type buttons', function () {

        it('specific quiz input remains visible after quiz type buttons are loaded', function (done) {
            window.fetch = function (url) {
                if (url.indexOf('/api/quiz-types') !== -1) {
                    return Promise.resolve({
                        ok: true,
                        json: function () {
                            return Promise.resolve([
                                { identifier: 'countries', displayName: 'Countries' }
                            ]);
                        }
                    });
                }
                return Promise.resolve({ ok: true, json: function () { return Promise.resolve({}); } });
            };

            loadQuizTypeButtons().then(function () {
                // The specific quiz input should still be in the DOM
                var input = document.getElementById('specificQuizId');
                var btn = document.getElementById('runSpecificQuizBtn');
                var label = fixtureContainer.querySelector('label[for="specificQuizId"]');

                expect(input).not.toBeNull();
                expect(btn).not.toBeNull();
                expect(label).toBeNull();
                done();
            }).catch(function (err) {
                done.fail(err);
            });
        });
    });
});
