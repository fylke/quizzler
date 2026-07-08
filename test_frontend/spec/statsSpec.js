describe('Stats Screen', function () {

    var statIds = [
        'statsCumulativeScore',
        'statsCompleted',
        'statsAverageScore'
    ];
    var statElements = {};
    var statsScreen;
    var adminLink;
    var originalQuizState;

    var mockStatsResponse = {
        cumulativeScore: 42,
        quizzesCompleted: 5,
        averageScore: 8.4
    };

    beforeEach(function () {
        // Set up DOM elements for stat cards
        statIds.forEach(function (id) {
            var el = document.getElementById(id);
            if (!el) {
                el = document.createElement('span');
                el.id = id;
                document.body.appendChild(el);
            }
            el.textContent = '0';
            statElements[id] = el;
        });

        statsScreen = document.getElementById('statsScreen');
        if (!statsScreen) {
            statsScreen = document.createElement('div');
            statsScreen.id = 'statsScreen';
            statsScreen.className = 'screen hidden';
            document.body.appendChild(statsScreen);
        }

        // Set up adminLink element
        adminLink = document.getElementById('adminLink');
        if (!adminLink) {
            adminLink = document.createElement('button');
            adminLink.id = 'adminLink';
            document.body.appendChild(adminLink);
        }
        adminLink.style.display = 'none';

        // Set global quizState
        originalQuizState = window.quizState;
        window.quizState = { user: { isAdmin: false } };
    });

    afterEach(function () {
        // Restore quizState
        window.quizState = originalQuizState;
    });

    // ========== Stat cards display correct values ==========
    describe('stat cards display', function () {
        it('displays correct values from API response', async function () {
            spyOn(window, 'fetch').and.returnValue(Promise.resolve({
                ok: true,
                json: function () {
                    return Promise.resolve(mockStatsResponse);
                }
            }));

            await showStatsScreen();

            expect(statElements['statsCumulativeScore'].textContent).toBe('42');
            expect(statElements['statsCompleted'].textContent).toBe('5');
            expect(statElements['statsAverageScore'].textContent).toBe('8.4');
            expect(statsScreen).not.toBeNull();
        });
    });

    // ========== Fetch failure leaves defaults ==========
    describe('fetch failure handling', function () {
        it('resets stale stat cards to default "0" on network error', async function () {
            statElements['statsCumulativeScore'].textContent = '42';
            statElements['statsCompleted'].textContent = '5';
            statElements['statsAverageScore'].textContent = '8.4';
            spyOn(window, 'fetch').and.returnValue(Promise.reject(new Error('Network error')));

            await showStatsScreen();

            statIds.forEach(function (id) {
                expect(statElements[id].textContent).toBe('0');
            });
        });

        it('resets stale stat cards to default "0" on non-ok response', async function () {
            statElements['statsCumulativeScore'].textContent = '42';
            statElements['statsCompleted'].textContent = '5';
            statElements['statsAverageScore'].textContent = '8.4';
            spyOn(window, 'fetch').and.returnValue(Promise.resolve({
                ok: false,
                json: function () {
                    return Promise.resolve({ error: 'Unauthorized' });
                }
            }));

            await showStatsScreen();

            statIds.forEach(function (id) {
                expect(statElements[id].textContent).toBe('0');
            });
        });
    });
});
