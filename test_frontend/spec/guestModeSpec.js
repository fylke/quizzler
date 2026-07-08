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
            hintImagesByDifficulty: {},
            unlockedHintDifficulties: [],
            liveHintDifficulty: null,
            liveRemainingGuesses: null,
            viewedHintDifficulty: null
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
});
