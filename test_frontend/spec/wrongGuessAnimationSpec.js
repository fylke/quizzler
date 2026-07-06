describe('Wrong Guess Animation', function () {
    var inputElement;
    var quizScreen;

    beforeEach(function () {
        inputElement = document.getElementById('answerInput');
        quizScreen = document.getElementById('quizScreen');
        // Clean up any leftover classes/styles from previous tests
        quizScreen.classList.remove('wrong-guess-shake', 'wrong-guess-glow', 'wrong-guess-static');
        quizScreen.style.removeProperty('transform');
        quizScreen.style.removeProperty('box-shadow');
        quizScreen.style.removeProperty('border-color');
        inputElement.value = '';
        inputElement.disabled = false;
    });

    // ========== animateWrongGuess adds animation classes ==========
    describe('animateWrongGuess applies animation classes', function () {
        beforeEach(function () {
            spyOn(window, 'matchMedia').and.returnValue({ matches: false });
        });

        it('adds .wrong-guess-shake class to the quiz screen', function () {
            animateWrongGuess(inputElement);
            expect(quizScreen.classList.contains('wrong-guess-shake')).toBe(true);
        });

        it('adds .wrong-guess-glow class to the quiz screen', function () {
            animateWrongGuess(inputElement);
            expect(quizScreen.classList.contains('wrong-guess-glow')).toBe(true);
        });
    });

    // ========== animationend removes animation classes ==========
    describe('animationend event cleanup', function () {
        beforeEach(function () {
            spyOn(window, 'matchMedia').and.returnValue({ matches: false });
        });

        it('removes .wrong-guess-shake after animationend fires', function () {
            animateWrongGuess(inputElement);
            expect(quizScreen.classList.contains('wrong-guess-shake')).toBe(true);

            var event = new Event('animationend');
            quizScreen.dispatchEvent(event);

            expect(quizScreen.classList.contains('wrong-guess-shake')).toBe(false);
        });

        it('removes .wrong-guess-glow after animationend fires', function () {
            animateWrongGuess(inputElement);
            expect(quizScreen.classList.contains('wrong-guess-glow')).toBe(true);

            var event = new Event('animationend');
            quizScreen.dispatchEvent(event);

            expect(quizScreen.classList.contains('wrong-guess-glow')).toBe(false);
        });
    });

    // ========== prefers-reduced-motion applies static class ==========
    describe('prefers-reduced-motion support', function () {
        beforeEach(function () {
            jasmine.clock().install();
            spyOn(window, 'matchMedia').and.returnValue({ matches: true });
        });

        afterEach(function () {
            jasmine.clock().uninstall();
        });

        it('applies .wrong-guess-static when reduced motion is preferred', function () {
            animateWrongGuess(inputElement);
            expect(quizScreen.classList.contains('wrong-guess-static')).toBe(true);
        });

        it('does not apply .wrong-guess-shake when reduced motion is preferred', function () {
            animateWrongGuess(inputElement);
            expect(quizScreen.classList.contains('wrong-guess-shake')).toBe(false);
        });

        it('does not apply .wrong-guess-glow when reduced motion is preferred', function () {
            animateWrongGuess(inputElement);
            expect(quizScreen.classList.contains('wrong-guess-glow')).toBe(false);
        });

        it('removes .wrong-guess-static after timeout', function () {
            animateWrongGuess(inputElement);
            expect(quizScreen.classList.contains('wrong-guess-static')).toBe(true);

            jasmine.clock().tick(1301);
            expect(quizScreen.classList.contains('wrong-guess-static')).toBe(false);
        });
    });

    // ========== Re-triggering mid-animation restarts ==========
    describe('re-triggering mid-animation', function () {
        beforeEach(function () {
            spyOn(window, 'matchMedia').and.returnValue({ matches: false });
        });

        it('re-applies animation classes when triggered again mid-animation', function () {
            animateWrongGuess(inputElement);
            expect(quizScreen.classList.contains('wrong-guess-shake')).toBe(true);
            expect(quizScreen.classList.contains('wrong-guess-glow')).toBe(true);

            // Trigger again without animationend firing
            animateWrongGuess(inputElement);
            expect(quizScreen.classList.contains('wrong-guess-shake')).toBe(true);
            expect(quizScreen.classList.contains('wrong-guess-glow')).toBe(true);
        });
    });

    // ========== Empty/whitespace submission calls animateWrongGuess ==========
    describe('empty/whitespace submission', function () {
        beforeEach(function () {
            jasmine.clock().install();
            spyOn(window, 'matchMedia').and.returnValue({ matches: false });
            spyOn(window, 'alert');
        });

        afterEach(function () {
            jasmine.clock().uninstall();
            submitting = false;
        });

        it('triggers animation on empty input submission', function () {
            inputElement.value = '';
            submitAnswer();
            expect(quizScreen.classList.contains('wrong-guess-shake')).toBe(true);
            expect(quizScreen.classList.contains('wrong-guess-glow')).toBe(true);
        });

        it('triggers animation on whitespace-only input submission', function () {
            inputElement.value = '   ';
            submitAnswer();
            expect(quizScreen.classList.contains('wrong-guess-shake')).toBe(true);
            expect(quizScreen.classList.contains('wrong-guess-glow')).toBe(true);
        });

        it('does not call alert() on empty submission', function () {
            inputElement.value = '';
            submitAnswer();
            expect(window.alert).not.toHaveBeenCalled();
        });
    });

    // ========== Wrong answer waits for shake before hint counters update ==========
    describe('wrong answer sequencing', function () {
        beforeEach(function () {
            spyOn(window, 'matchMedia').and.returnValue({ matches: false });
            spyOn(window, 'fetch').and.callFake(function () {
                return Promise.resolve({
                    ok: true,
                    json: function () {
                        return Promise.resolve({
                            correct: false,
                            remainingGuesses: 2,
                            hint: 'Next hint',
                            hintDifficulty: 4,
                            images: ['/media/countries/1/4a.jpg', '/media/countries/1/4b.jpg']
                        });
                    }
                });
            });
            spyOn(window, 'updateHintDisplay').and.callFake(function () {});
            spyOn(window, 'renderQuizImages').and.callFake(function () {});
            inputElement.value = 'wrong answer';
        });

        afterEach(function () {
            submitting = false;
        });

        it('defers hint update until the animation has ended', function (done) {
            var submissionPromise = submitAnswer();

            setTimeout(function () {
                expect(window.updateHintDisplay).not.toHaveBeenCalled();

                quizScreen.dispatchEvent(new Event('animationend'));

                submissionPromise.then(function () {
                    expect(window.updateHintDisplay).toHaveBeenCalled();
                    done();
                }).catch(function (error) {
                    done.fail(error);
                });
            }, 0);
        });
    });

    // ========== Input remains enabled and focusable during animation ==========
    describe('input state during animation', function () {
        beforeEach(function () {
            spyOn(window, 'matchMedia').and.returnValue({ matches: false });
        });

        it('input is not disabled during animation', function () {
            animateWrongGuess(inputElement);
            expect(inputElement.disabled).toBe(false);
        });

        it('input is focusable during animation', function () {
            animateWrongGuess(inputElement);
            inputElement.focus();
            expect(document.activeElement).toBe(inputElement);
        });
    });

    // ========== alert() is never called in wrong-guess or empty-submission paths ==========
    describe('alert() is never called', function () {
        beforeEach(function () {
            jasmine.clock().install();
            spyOn(window, 'matchMedia').and.returnValue({ matches: false });
            spyOn(window, 'alert');
        });

        afterEach(function () {
            jasmine.clock().uninstall();
            submitting = false;
        });

        it('does not call alert() when empty input is submitted', function () {
            inputElement.value = '';
            submitAnswer();
            expect(window.alert).not.toHaveBeenCalled();
        });

        it('does not call alert() when whitespace input is submitted', function () {
            inputElement.value = '    \t  ';
            submitAnswer();
            expect(window.alert).not.toHaveBeenCalled();
        });

        it('does not call alert() when animateWrongGuess is called directly', function () {
            animateWrongGuess(inputElement);
            expect(window.alert).not.toHaveBeenCalled();
        });
    });

    // ========== Focus style preserved after animation ends ==========
    describe('focus style preservation after animation', function () {
        beforeEach(function () {
            spyOn(window, 'matchMedia').and.returnValue({ matches: false });
        });

        it('removes all animation inline styles after animationend', function () {
            animateWrongGuess(inputElement);

            var event = new Event('animationend');
            quizScreen.dispatchEvent(event);

            // No residual inline styles from animation
            expect(quizScreen.style.getPropertyValue('transform')).toBe('');
            expect(quizScreen.style.getPropertyValue('box-shadow')).toBe('');
            expect(quizScreen.style.getPropertyValue('border-color')).toBe('');
        });

        it('input remains focusable after animation ends', function () {
            inputElement.focus();
            animateWrongGuess(inputElement);

            var event = new Event('animationend');
            quizScreen.dispatchEvent(event);

            // Input should still be focused
            expect(document.activeElement).toBe(inputElement);
        });

        it('no animation classes remain after animationend', function () {
            inputElement.focus();
            animateWrongGuess(inputElement);

            var event = new Event('animationend');
            quizScreen.dispatchEvent(event);

            expect(quizScreen.classList.contains('wrong-guess-shake')).toBe(false);
            expect(quizScreen.classList.contains('wrong-guess-glow')).toBe(false);
        });
    });
});
