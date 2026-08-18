describe('Quiz sharing', function () {
    var originalShareDescriptor;
    var originalClipboardDescriptor;

    beforeEach(function () {
        originalShareDescriptor = Object.getOwnPropertyDescriptor(navigator, 'share');
        originalClipboardDescriptor = Object.getOwnPropertyDescriptor(navigator, 'clipboard');
        quizState.currentQuizGuid = '11111111-1111-4111-8111-111111111111';
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

    it('uses Web Share with a GUID deep link when available', async function () {
        var shareSpy = jasmine.createSpy('share').and.returnValue(Promise.resolve());
        Object.defineProperty(navigator, 'share', {
            configurable: true,
            value: shareSpy
        });

        await shareCurrentQuiz();

        expect(shareSpy).toHaveBeenCalled();
        var payload = shareSpy.calls.mostRecent().args[0];
        expect(payload.url).toContain('?quiz=11111111-1111-4111-8111-111111111111');
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
            '?quiz=11111111-1111-4111-8111-111111111111'
        );
        expect(document.getElementById('appNotification').textContent).toContain('copied');
    });
});