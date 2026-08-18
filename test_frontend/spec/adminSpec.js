describe('Admin Panel', function () {

    // ========== escapeHtml ==========
    describe('escapeHtml', function () {
        it('escapes angle brackets', function () {
            expect(escapeHtml('<script>')).toBe('&lt;script&gt;');
        });

        it('escapes ampersands', function () {
            expect(escapeHtml('a & b')).toBe('a &amp; b');
        });

        it('does not alter double quotes (they are safe in text content)', function () {
            expect(escapeHtml('"hello"')).toBe('"hello"');
        });

        it('returns plain text unchanged', function () {
            expect(escapeHtml('hello world')).toBe('hello world');
        });

        it('handles empty string', function () {
            expect(escapeHtml('')).toBe('');
        });
    });

    describe('quiz type routing', function () {
        afterEach(function () {
            currentAdminQuizType = 'countries';
            currentAdminQuizTypeName = 'Countries';
        });

        it('uses generic admin question routes for additional types', function () {
            currentAdminQuizType = 'cities';
            expect(adminQuestionsUrl()).toMatch(/\/api\/admin\/quiz-types\/cities\/questions$/);
            expect(adminQuestionsUrl(7)).toMatch(/\/api\/admin\/quiz-types\/cities\/questions\/7$/);
        });
    });

    // ========== escapeAttr ==========
    describe('escapeAttr', function () {
        it('escapes double quotes', function () {
            expect(escapeAttr('say "hi"')).toBe('say &quot;hi&quot;');
        });

        it('escapes angle brackets', function () {
            expect(escapeAttr('<div>')).toBe('&lt;div&gt;');
        });

        it('escapes ampersands', function () {
            expect(escapeAttr('a & b')).toBe('a &amp; b');
        });

        it('handles empty string', function () {
            expect(escapeAttr('')).toBe('');
        });

        it('returns plain text unchanged', function () {
            expect(escapeAttr('hello')).toBe('hello');
        });
    });

    // ========== addImageField ==========
    describe('addImageField', function () {
        var container;

        beforeEach(function () {
            container = document.createElement('div');
            container.id = 'adminImagesContainer';
            document.body.appendChild(container);
        });

        afterEach(function () {
            container.remove();
        });

        it('adds an input row to the container', function () {
            addImageField('https://example.com/img.jpg');
            expect(container.querySelectorAll('.admin-dynamic-field-row').length).toBe(1);
        });

        it('sets the input value to the provided value', function () {
            addImageField('https://example.com/img.jpg');
            var input = container.querySelector('input');
            expect(input.value).toBe('https://example.com/img.jpg');
        });

        it('sets empty value when called with empty string', function () {
            addImageField('');
            var input = container.querySelector('input');
            expect(input.value).toBe('');
        });

        it('adds a remove button', function () {
            addImageField('test');
            var btn = container.querySelector('button');
            expect(btn).not.toBeNull();
            expect(btn.textContent).toContain('✕');
        });

        it('adds multiple rows when called multiple times', function () {
            addImageField('url1');
            addImageField('url2');
            addImageField('url3');
            expect(container.querySelectorAll('.admin-dynamic-field-row').length).toBe(3);
        });
    });

    // ========== addAnswerField ==========
    describe('addAnswerField', function () {
        var container;

        beforeEach(function () {
            container = document.createElement('div');
            container.id = 'adminAnswersContainer';
            document.body.appendChild(container);
        });

        afterEach(function () {
            container.remove();
        });

        it('adds an input row to the container', function () {
            addAnswerField('Paris');
            expect(container.querySelectorAll('.admin-dynamic-field-row').length).toBe(1);
        });

        it('sets the input value', function () {
            addAnswerField('Paris');
            var input = container.querySelector('input');
            expect(input.value).toBe('Paris');
        });

        it('adds a remove button', function () {
            addAnswerField('Tokyo');
            var btn = container.querySelector('button');
            expect(btn).not.toBeNull();
        });
    });

    // ========== removeImageField / removeAnswerField ==========
    describe('removeImageField / removeAnswerField', function () {
        var container;

        beforeEach(function () {
            container = document.createElement('div');
            container.id = 'adminImagesContainer';
            document.body.appendChild(container);
        });

        afterEach(function () {
            container.remove();
        });

        it('removes the parent element of the button (removeImageField)', function () {
            addImageField('url1');
            addImageField('url2');
            expect(container.querySelectorAll('.admin-dynamic-field-row').length).toBe(2);

            var btn = container.querySelector('.admin-dynamic-field-row button');
            removeImageField(btn);
            expect(container.querySelectorAll('.admin-dynamic-field-row').length).toBe(1);
        });

        it('removes the parent element of the button (removeAnswerField)', function () {
            var ansContainer = document.createElement('div');
            ansContainer.id = 'adminAnswersContainer';
            document.body.appendChild(ansContainer);

            addAnswerField('Answer1');
            addAnswerField('Answer2');
            expect(ansContainer.querySelectorAll('.admin-dynamic-field-row').length).toBe(2);

            var btn = ansContainer.querySelector('.admin-dynamic-field-row button');
            removeAnswerField(btn);
            expect(ansContainer.querySelectorAll('.admin-dynamic-field-row').length).toBe(1);

            ansContainer.remove();
        });
    });

    // ========== showAdminError ==========
    describe('showAdminError', function () {
        var errorEl;

        beforeEach(function () {
            jasmine.clock().install();
            errorEl = document.createElement('div');
            errorEl.id = 'adminError';
            errorEl.style.display = 'none';
            document.body.appendChild(errorEl);
        });

        afterEach(function () {
            jasmine.clock().uninstall();
            errorEl.remove();
        });

        it('displays the error message', function () {
            showAdminError('Something went wrong');
            expect(errorEl.textContent).toBe('Something went wrong');
        });

        it('makes the element visible', function () {
            showAdminError('Error!');
            expect(errorEl.style.display).toBe('block');
        });

        it('auto-hides after 5 seconds', function () {
            showAdminError('Temporary error');
            expect(errorEl.style.display).toBe('block');
            jasmine.clock().tick(5001);
            expect(errorEl.style.display).toBe('none');
        });
    });

    // ========== showAdminSuccess ==========
    describe('showAdminSuccess', function () {
        var successEl;

        beforeEach(function () {
            jasmine.clock().install();
            successEl = document.createElement('div');
            successEl.id = 'adminSuccess';
            successEl.style.display = 'none';
            document.body.appendChild(successEl);
        });

        afterEach(function () {
            jasmine.clock().uninstall();
            successEl.remove();
        });

        it('displays the success message', function () {
            showAdminSuccess('Saved!');
            expect(successEl.textContent).toBe('Saved!');
        });

        it('makes the element visible', function () {
            showAdminSuccess('Done');
            expect(successEl.style.display).toBe('block');
        });

        it('auto-hides after 3 seconds', function () {
            showAdminSuccess('Success');
            expect(successEl.style.display).toBe('block');
            jasmine.clock().tick(3001);
            expect(successEl.style.display).toBe('none');
        });
    });

    // ========== hideDeleteDialog ==========
    describe('hideDeleteDialog', function () {
        var dialog;

        beforeEach(function () {
            dialog = document.createElement('div');
            dialog.id = 'adminDeleteDialog';
            dialog.style.display = 'flex';
            document.body.appendChild(dialog);
        });

        afterEach(function () {
            dialog.remove();
        });

        it('hides the dialog', function () {
            hideDeleteDialog();
            expect(dialog.style.display).toBe('none');
        });
    });

    // ========== loadDestinations ==========
    describe('loadDestinations', function () {
        var listEl, countEl, emptyEl, errorEl;

        beforeEach(function () {
            listEl = document.createElement('div');
            listEl.id = 'adminDestList';
            document.body.appendChild(listEl);

            countEl = document.createElement('p');
            countEl.id = 'adminDestCount';
            document.body.appendChild(countEl);

            emptyEl = document.createElement('p');
            emptyEl.id = 'adminEmptyState';
            emptyEl.style.display = 'none';
            document.body.appendChild(emptyEl);

            errorEl = document.createElement('div');
            errorEl.id = 'adminError';
            errorEl.style.display = 'none';
            document.body.appendChild(errorEl);
        });

        afterEach(function () {
            listEl.remove();
            countEl.remove();
            emptyEl.remove();
            errorEl.remove();
        });

        it('fetches from /api/admin/destinations', async function () {
            spyOn(window, 'fetch').and.returnValue(Promise.resolve({
                ok: true,
                json: function () {
                    return Promise.resolve({ destinations: [], count: 0 });
                }
            }));

            await loadDestinations();
            expect(window.fetch).toHaveBeenCalledWith(jasmine.stringMatching(/\/api\/admin\/destinations$/));
        });

        it('renders destination items on success', async function () {
            spyOn(window, 'fetch').and.returnValue(Promise.resolve({
                ok: true,
                json: function () {
                    return Promise.resolve({
                        destinations: [
                            { id: 1, name: 'Paris' },
                            { id: 2, name: 'Tokyo' }
                        ],
                        count: 2
                    });
                }
            }));

            await loadDestinations();
            expect(listEl.querySelectorAll('.admin-dest-item').length).toBe(2);
            expect(countEl.textContent).toContain('2');
        });

        it('shows empty state when count is 0', async function () {
            spyOn(window, 'fetch').and.returnValue(Promise.resolve({
                ok: true,
                json: function () {
                    return Promise.resolve({ destinations: [], count: 0 });
                }
            }));

            await loadDestinations();
            expect(emptyEl.style.display).toBe('block');
            expect(listEl.innerHTML).toBe('');
        });

        it('shows error on fetch failure', async function () {
            spyOn(window, 'fetch').and.returnValue(Promise.resolve({
                ok: false,
                json: function () {
                    return Promise.resolve({ error: 'Unauthorized' });
                }
            }));

            await loadDestinations();
            expect(errorEl.textContent).toContain('Unauthorized');
            expect(errorEl.style.display).toBe('block');
        });

        it('shows error on network exception', async function () {
            spyOn(window, 'fetch').and.returnValue(Promise.reject(new Error('Network error')));

            await loadDestinations();
            expect(errorEl.textContent).toContain('Could not connect');
            expect(errorEl.style.display).toBe('block');
        });
    });

    // ========== saveDestination - validation ==========
    describe('saveDestination - validation', function () {
        var errorEl, nameInput, hintInputs, imagesContainer, answersContainer;

        beforeEach(function () {
            jasmine.clock().install();

            errorEl = document.createElement('div');
            errorEl.id = 'adminError';
            errorEl.style.display = 'none';
            document.body.appendChild(errorEl);

            nameInput = document.createElement('input');
            nameInput.id = 'adminDestName';
            document.body.appendChild(nameInput);

            hintInputs = [];
            for (var i = 1; i <= 5; i++) {
                var textarea = document.createElement('textarea');
                textarea.id = 'adminHint' + i;
                document.body.appendChild(textarea);
                hintInputs.push(textarea);
            }

            imagesContainer = document.createElement('div');
            imagesContainer.id = 'adminImagesContainer';
            document.body.appendChild(imagesContainer);

            answersContainer = document.createElement('div');
            answersContainer.id = 'adminAnswersContainer';
            document.body.appendChild(answersContainer);
        });

        afterEach(function () {
            jasmine.clock().uninstall();
            errorEl.remove();
            nameInput.remove();
            hintInputs.forEach(function (el) { el.remove(); });
            imagesContainer.remove();
            answersContainer.remove();
        });

        it('shows error when name is empty', async function () {
            nameInput.value = '';
            hintInputs.forEach(function (el) { el.value = 'hint'; });

            await saveDestination();
            expect(errorEl.textContent).toContain('Name is required');
            expect(errorEl.style.display).toBe('block');
        });

        it('shows error when hints are missing', async function () {
            nameInput.value = 'Test Destination';
            hintInputs[0].value = 'Hint 1';
            // Leave other hints empty

            await saveDestination();
            expect(errorEl.textContent).toContain('Hint');
            expect(errorEl.textContent).toContain('required');
            expect(errorEl.style.display).toBe('block');
        });

        it('shows error when fewer than 2 images', async function () {
            nameInput.value = 'Test';
            hintInputs.forEach(function (el) { el.value = 'A hint'; });
            // Add only 1 image
            addImageField('https://example.com/img1.jpg');

            // Add at least 1 answer
            addAnswerField('Answer');

            await saveDestination();
            expect(errorEl.textContent).toContain('image');
            expect(errorEl.style.display).toBe('block');
        });

        it('shows error when no answers provided', async function () {
            nameInput.value = 'Test';
            hintInputs.forEach(function (el) { el.value = 'A hint'; });
            // Add 2 images
            addImageField('https://example.com/img1.jpg');
            addImageField('https://example.com/img2.jpg');
            // No answers

            await saveDestination();
            expect(errorEl.textContent).toContain('answer');
            expect(errorEl.style.display).toBe('block');
        });

        it('shows error when name exceeds 128 characters', async function () {
            nameInput.value = 'x'.repeat(129);
            hintInputs.forEach(function (el) { el.value = 'A hint'; });

            await saveDestination();
            expect(errorEl.textContent).toContain('128');
            expect(errorEl.style.display).toBe('block');
        });
    });
});
