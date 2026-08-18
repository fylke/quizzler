describe('Quiz sharing', function () {
    var originalShareDescriptor;
    var originalClipboardDescriptor;

    beforeEach(function () {
        originalShareDescriptor = Object.getOwnPropertyDescriptor(navigator, 'share');
        originalClipboardDescriptor = Object.getOwnPropertyDescriptor(navigator, 'clipboard');
        quizState.currentQuizGuid = 'c1';
    });

    afterEach(function () {
        if (originalShareDescriptor) {
            Object.defineProperty(navigator, 'share', originalShareDescriptor);
        } else {
            delete navigator.share;
        }
        if (originalClipboardDescriptor) {
            Object.defineProperty(navigator, 'clipboard', originalClipboardDescriptor);
        } else {
            delete navigator.clipboard;
        }
        document.getElementById('appNotification')?.remove();
    });

    it('copies a GUID deep link even when Web Share is available', async function () {
        var shareSpy = jasmine.createSpy('share').and.returnValue(Promise.resolve());
        var writeTextSpy = jasmine.createSpy('writeText').and.returnValue(Promise.resolve());
        Object.defineProperty(navigator, 'share', {
            configurable: true,
            value: shareSpy
        });
        Object.defineProperty(navigator, 'clipboard', {
            configurable: true,
            value: { writeText: writeTextSpy }
        });

        await shareCurrentQuiz();

        expect(shareSpy).not.toHaveBeenCalled();
        expect(writeTextSpy).toHaveBeenCalled();
        expect(writeTextSpy.calls.mostRecent().args[0]).toContain(
            '/quiz/c1'
        );
    });

    it('copies the GUID deep link when Web Share is unavailable', async function () {
        var writeTextSpy = jasmine.createSpy('writeText').and.returnValue(Promise.resolve());
        Object.defineProperty(navigator, 'share', {
            configurable: true,
            value: undefined
        });
        Object.defineProperty(navigator, 'clipboard', {
            configurable: true,
            value: { writeText: writeTextSpy }
        });

        await shareCurrentQuiz();

        expect(writeTextSpy).toHaveBeenCalled();
        expect(writeTextSpy.calls.mostRecent().args[0]).toContain(
            '/quiz/c1'
        );
        expect(document.getElementById('appNotification').textContent).toContain('copied');
    });
});