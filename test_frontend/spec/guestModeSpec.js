describe('Guest Mode', function () {
    var originalQuizState;
    var originalFetch;
    var guestRestrictionsStatus;
    var adminLink;

    beforeEach(function () {
        originalQuizState = quizState;
        originalFetch = window.fetch;
        quizState = {
            user: null,
            isGuest: false,
            currentQuizId: null,
            hintHistory: {},
            currentHint: {
                difficulty: null,
                remainingGuesses: null,
                viewedDifficulty: null
            }
        };

        guestRestrictionsStatus = document.getElementById('guestRestrictionsStatus');
        if (!guestRestrictionsStatus) {
            guestRestrictionsStatus = document.createElement('p');
            guestRestrictionsStatus.id = 'guestRestrictionsStatus';
            guestRestrictionsStatus.className = 'hidden';
            document.body.appendChild(guestRestrictionsStatus);
        }

        adminLink = document.getElementById('adminLink');
        if (!adminLink) {
            adminLink = document.createElement('button');
            adminLink.id = 'adminLink';
            document.body.appendChild(adminLink);
        }
        adminLink.style.display = 'none';

        ['statsCumulativeScore', 'statsCompleted', 'statsAverageScore'].forEach(function (id) {
            var el = document.getElementById(id);
            if (!el) {
                el = document.createElement('span');
                el.id = id;
                document.body.appendChild(el);
            }
            el.textContent = '0';
        });

        var statsScreen = document.getElementById('statsScreen');
        if (!statsScreen) {
            statsScreen = document.createElement('div');
            statsScreen.id = 'statsScreen';
            statsScreen.className = 'screen hidden';
            document.body.appendChild(statsScreen);
        }
    });

    afterEach(function () {
        quizState = originalQuizState;
        window.fetch = originalFetch;
    });

    it('continueAsGuest stores guest identity and shows status when no active quiz exists', async function () {
        spyOn(window, 'restoreActiveQuiz').and.returnValue(Promise.resolve(false));
        spyOn(window, 'showStatusScreen').and.returnValue(Promise.resolve());
        spyOn(window, 'fetch').and.returnValue(Promise.resolve({
            ok: true,
            json: function () {
                return Promise.resolve({
                    guest: { id: 7, name: 'Guest #7', isGuest: true }
                });
            }
        }));

        await continueAsGuest();

        expect(quizState.isGuest).toBe(true);
        expect(quizState.user.id).toBe(7);
        expect(window.showStatusScreen).toHaveBeenCalled();
    });

    it('showStatsScreen shows guest restrictions for guest users', async function () {
        quizState.user = { id: 7, isAdmin: false };
        quizState.isGuest = true;
        spyOn(window, 'fetch').and.returnValue(Promise.resolve({
            ok: true,
            json: function () {
                return Promise.resolve({
                    cumulativeScore: 0,
                    quizzesCompleted: 0,
                    averageScore: 0
                });
            }
        }));

        await showStatsScreen();

        expect(guestRestrictionsStatus.classList.contains('hidden')).toBe(false);
    });

    it('showStatsScreen hides guest restrictions for signed-in users', async function () {
        quizState.user = { id: 8, isAdmin: false };
        quizState.isGuest = false;
        guestRestrictionsStatus.classList.remove('hidden');
        spyOn(window, 'fetch').and.returnValue(Promise.resolve({
            ok: true,
            json: function () {
                return Promise.resolve({
                    cumulativeScore: 0,
                    quizzesCompleted: 0,
                    averageScore: 0
                });
            }
        }));

        await showStatsScreen();

        expect(guestRestrictionsStatus.classList.contains('hidden')).toBe(true);
    });

    it('restoreGuestSession returns false when no guest cookie-backed session exists', async function () {
        spyOn(window, 'fetch').and.returnValue(Promise.resolve({
            status: 404,
            ok: false
        }));

        var restored = await restoreGuestSession();

        expect(restored).toBe(false);
    });

    it('showMainScreen hides logout button for guest users', async function () {
        var statusScreen = document.getElementById('statusScreen');
        if (!statusScreen) {
            statusScreen = document.createElement('div');
            statusScreen.id = 'statusScreen';
            document.body.appendChild(statusScreen);
        }

        var logoutBtn = document.getElementById('logoutBtn');
        if (!logoutBtn) {
            logoutBtn = document.createElement('button');
            logoutBtn.id = 'logoutBtn';
            document.body.appendChild(logoutBtn);
        }

        var statusLoginLink = document.getElementById('statusLoginLink');
        if (!statusLoginLink) {
            statusLoginLink = document.createElement('a');
            statusLoginLink.id = 'statusLoginLink';
            statusLoginLink.className = 'hidden';
            document.body.appendChild(statusLoginLink);
        }

        quizState.user = { id: 7, isAdmin: false };
        quizState.isGuest = true;

        spyOn(window, 'loadQuizTypeButtons').and.returnValue(Promise.resolve());

        await showMainScreen();

        expect(logoutBtn.style.display).toBe('none');
        expect(statusLoginLink.classList.contains('hidden')).toBe(false);
    });

    it('showMainScreen shows logout button for signed-in users', async function () {
        var statusScreen = document.getElementById('statusScreen');
        if (!statusScreen) {
            statusScreen = document.createElement('div');
            statusScreen.id = 'statusScreen';
            document.body.appendChild(statusScreen);
        }

        var logoutBtn = document.getElementById('logoutBtn');
        if (!logoutBtn) {
            logoutBtn = document.createElement('button');
            logoutBtn.id = 'logoutBtn';
            document.body.appendChild(logoutBtn);
        }

        var statusLoginLink = document.getElementById('statusLoginLink');
        if (!statusLoginLink) {
            statusLoginLink = document.createElement('a');
            statusLoginLink.id = 'statusLoginLink';
            statusLoginLink.className = 'hidden';
            document.body.appendChild(statusLoginLink);
        }

        quizState.user = { id: 8, isAdmin: false };
        quizState.isGuest = false;

        spyOn(window, 'loadQuizTypeButtons').and.returnValue(Promise.resolve());

        await showMainScreen();

        expect(logoutBtn.style.display).toBe('');
        expect(statusLoginLink.classList.contains('hidden')).toBe(true);
    });
});
