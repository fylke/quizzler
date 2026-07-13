// Feature: quiz-type-selection, Property 5: Button labels match quiz type display names
describe('Quiz Type Buttons - Property Tests', function () {

    // **Validates: Requirements 2.3**

    var originalFetch;
    var fixtureContainer;

    beforeEach(function () {
        // Save original fetch
        originalFetch = window.fetch;

        // Remove any leftover quiz type container
        var existing = document.getElementById('quizTypeButtonsContainer');
        if (existing) {
            existing.remove();
        }

        // Create a fixture container that includes .quiz-actions with the runRandomQuizBtn
        fixtureContainer = document.createElement('div');
        fixtureContainer.id = 'quizTypeButtonsFixture';
        fixtureContainer.innerHTML =
            '<div class="quiz-actions">' +
                '<button id="runRandomQuizBtn">Run Random Quiz</button>' +
                '<button id="adminLink" style="display:none;">Admin Panel</button>' +
                '<button id="logoutBtn">Logout</button>' +
            '</div>';
        document.body.appendChild(fixtureContainer);
    });

    afterEach(function () {
        // Restore original fetch
        window.fetch = originalFetch;

        // Clean up fixture
        if (fixtureContainer && fixtureContainer.parentNode) {
            fixtureContainer.remove();
        }

        // Clean up any notifications
        var notification = document.getElementById('appNotification');
        if (notification) {
            notification.remove();
        }
    });

    function mockFetchSuccess(quizTypes) {
        window.fetch = function () {
            return Promise.resolve({
                ok: true,
                json: function () {
                    return Promise.resolve(quizTypes);
                }
            });
        };
    }

    function mockFetchFailure() {
        window.fetch = function () {
            return Promise.reject(new Error('Network error'));
        };
    }

    function mockFetchNonOk() {
        window.fetch = function () {
            return Promise.resolve({
                ok: false,
                status: 500,
                json: function () {
                    return Promise.resolve({ error: 'Server error' });
                }
            });
        };
    }

    describe('Property 5: Button labels match quiz type display names', function () {

        it('each button text matches the displayName from quiz type data', function (done) {
            var quizTypes = [
                { identifier: 'countries', displayName: 'Countries' },
                { identifier: 'cities', displayName: 'Cities' },
                { identifier: 'territories', displayName: 'Territories' }
            ];

            mockFetchSuccess(quizTypes);

            loadQuizTypeButtons().then(function () {
                var buttons = document.querySelectorAll('.quiz-type-btn');
                var sortedNames = quizTypes.map(function (t) { return t.displayName; }).sort(function (a, b) {
                    return a.localeCompare(b);
                });

                expect(buttons.length).toBe(quizTypes.length);
                for (var i = 0; i < buttons.length; i++) {
                    expect(buttons[i].textContent).toBe(sortedNames[i]);
                }
                done();
            }).catch(function (err) {
                done.fail(err);
            });
        });

        it('buttons are sorted alphabetically by displayName', function (done) {
            var quizTypes = [
                { identifier: 'territories', displayName: 'Territories' },
                { identifier: 'cities', displayName: 'Cities' },
                { identifier: 'countries', displayName: 'Countries' }
            ];

            mockFetchSuccess(quizTypes);

            loadQuizTypeButtons().then(function () {
                var buttons = document.querySelectorAll('.quiz-type-btn');
                var labels = [];
                for (var i = 0; i < buttons.length; i++) {
                    labels.push(buttons[i].textContent);
                }
                var sorted = labels.slice().sort(function (a, b) {
                    return a.localeCompare(b);
                });
                expect(labels).toEqual(sorted);
                done();
            }).catch(function (err) {
                done.fail(err);
            });
        });

        it('property: for any list of displayNames, buttons match exactly (fast-check)', function (done) {
            var assertion = fc.assert(
                fc.asyncProperty(
                    fc.array(
                        fc.record({
                            identifier: fc.stringOf(
                                fc.constantFrom('a','b','c','d','e','f','g','h','i','j','k','l','m',
                                    'n','o','p','q','r','s','t','u','v','w','x','y','z',
                                    '0','1','2','3','4','5','6','7','8','9','-'),
                                { minLength: 1, maxLength: 10 }
                            ).filter(function (s) {
                                return /^[a-z][a-z0-9-]*$/.test(s);
                            }),
                            displayName: fc.stringOf(
                                fc.constantFrom('A','B','C','D','E','F','G','H','I','J','K','L','M',
                                    'N','O','P','Q','R','S','T','U','V','W','X','Y','Z',
                                    'a','b','c','d','e','f','g','h','i','j','k','l','m',
                                    'n','o','p','q','r','s','t','u','v','w','x','y','z',
                                    '0','1','2','3','4','5','6','7','8','9',' '),
                                { minLength: 1, maxLength: 20 }
                            )
                        }),
                        { minLength: 1, maxLength: 5 }
                    ),
                    function (quizTypes) {
                        // Ensure unique identifiers
                        var seen = {};
                        var unique = quizTypes.filter(function (t) {
                            if (seen[t.identifier]) return false;
                            seen[t.identifier] = true;
                            return true;
                        });

                        mockFetchSuccess(unique);

                        return loadQuizTypeButtons().then(function () {
                            var buttons = document.querySelectorAll('.quiz-type-btn');
                            // Use localeCompare to match the implementation's sorting
                            var expectedNames = unique.map(function (t) { return t.displayName; }).sort(function (a, b) {
                                return a.localeCompare(b);
                            });

                            expect(buttons.length).toBe(expectedNames.length);
                            for (var i = 0; i < buttons.length; i++) {
                                expect(buttons[i].textContent).toBe(expectedNames[i]);
                            }
                        });
                    }
                ),
                { numRuns: 50 }
            );

            assertion.then(function () {
                done();
            }).catch(function (err) {
                done.fail(err);
            });
        });

        it('single quiz type renders exactly one button with correct label', function (done) {
            var quizTypes = [
                { identifier: 'countries', displayName: 'Countries' }
            ];

            mockFetchSuccess(quizTypes);

            loadQuizTypeButtons().then(function () {
                var buttons = document.querySelectorAll('.quiz-type-btn');
                expect(buttons.length).toBe(1);
                expect(buttons[0].textContent).toBe('Countries');
                done();
            }).catch(function (err) {
                done.fail(err);
            });
        });

        it('adds the countries hover text only to the countries button', function (done) {
            var quizTypes = [
                { identifier: 'cities', displayName: 'Cities' },
                { identifier: 'countries', displayName: 'Countries' }
            ];

            mockFetchSuccess(quizTypes);

            loadQuizTypeButtons().then(function () {
                var buttons = document.querySelectorAll('.quiz-type-btn');
                var countriesButton = Array.prototype.find.call(buttons, function (button) {
                    return button.textContent === 'Countries';
                });
                var citiesButton = Array.prototype.find.call(buttons, function (button) {
                    return button.textContent === 'Cities';
                });

                expect(countriesButton).not.toBeNull();
                expect(countriesButton.title).toBe('Guess the country based on a text- and two picture hints. You have 5 hint levels and 3 guesses.');
                expect(citiesButton).not.toBeNull();
                expect(citiesButton.title).toBe('');
                done();
            }).catch(function (err) {
                done.fail(err);
            });
        });
    });

    describe('Empty quiz type list', function () {

        it('shows "No quiz types are currently available" message', function (done) {
            mockFetchSuccess([]);

            loadQuizTypeButtons().then(function () {
                var container = document.getElementById('quizTypeButtonsContainer');
                expect(container).not.toBeNull();
                expect(container.textContent).toContain('No quiz types are currently available');

                var buttons = document.querySelectorAll('.quiz-type-btn');
                expect(buttons.length).toBe(0);
                done();
            }).catch(function (err) {
                done.fail(err);
            });
        });
    });

    describe('Fetch failure', function () {

        it('shows notification when fetch rejects', function (done) {
            mockFetchFailure();

            loadQuizTypeButtons().then(function () {
                // Check that notification was shown
                var notification = document.getElementById('appNotification');
                expect(notification).not.toBeNull();
                expect(notification.textContent).toContain('Could not load quiz types');
                done();
            }).catch(function (err) {
                done.fail(err);
            });
        });

        it('shows notification when fetch returns non-ok response', function (done) {
            mockFetchNonOk();

            loadQuizTypeButtons().then(function () {
                var notification = document.getElementById('appNotification');
                expect(notification).not.toBeNull();
                expect(notification.textContent).toContain('Could not load quiz types');
                done();
            }).catch(function (err) {
                done.fail(err);
            });
        });
    });
});
