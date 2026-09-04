describe('Image Enlargement', function () {
    var fixtureContainer;

    beforeEach(function () {
        fixtureContainer = document.createElement('div');
        fixtureContainer.id = 'imageEnlargeFixture';
        fixtureContainer.innerHTML =
            '<div id="quizScreen" class="screen">' +
                '<div class="hint-section"><h2 id="hint"></h2></div>' +
                '<div class="hint-meta">' +
                    '<span id="hintProgress"></span>' +
                    '<span id="hintPoints"></span>' +
                '</div>' +
                '<div class="hint-review hidden" id="hintReviewSection">' +
                    '<span class="hint-review-label">Review unlocked hints:</span>' +
                    '<div id="hintHistoryButtons" class="hint-history-buttons"></div>' +
                '</div>' +
                '<input id="answerInput" />' +
                '<div id="progressFill"></div>' +
                '<img id="image1" />' +
                '<img id="image2" />' +
            '</div>' +
            '<div id="resultsScreen" class="screen hidden">' +
                '<div id="resultsStatus"></div>' +
                '<div id="resultsDetails"></div>' +
                '<h3 id="resultsImagesHeading" class="hidden"></h3>' +
                '<div id="resultsImages" class="images-section hidden"></div>' +
                '<section id="resultsHintReview" class="results-hint-review hidden"></section>' +
            '</div>' +
            '<div id="imageModal" class="modal-overlay" style="display:none;" role="dialog" aria-modal="true" aria-label="Enlarged image">' +
                '<div class="modal-card image-modal-card">' +
                    '<button id="imageModalPrevBtn" type="button" class="image-modal-nav image-modal-nav-prev" aria-label="Show previous hint image">&#8249;</button>' +
                    '<button id="imageModalNextBtn" type="button" class="image-modal-nav image-modal-nav-next" aria-label="Show next hint image">&#8250;</button>' +
                    '<button id="imageModalCloseBtn" type="button" class="image-modal-close" aria-label="Close enlarged image">×</button>' +
                    '<div id="imageModalMedia" class="image-modal-media">' +
                        '<img id="imageModalImage" src="" alt="" class="image-modal-image">' +
                    '</div>' +
                '</div>' +
            '</div>';
        document.body.appendChild(fixtureContainer);

        resetHintReviewState();
    });

    afterEach(function () {
        resetHintReviewState();
        if (fixtureContainer && fixtureContainer.parentNode) {
            fixtureContainer.remove();
        }
    });

    it('opens the quiz image in a modal when clicked', function () {
        displayQuiz({
            id: 17,
            hint: 'Test hint',
            hintDifficulty: 5,
            remainingGuesses: 3,
            images: ['https://example.com/quiz-1.jpg', 'https://example.com/quiz-2.jpg']
        });

        document.getElementById('image1').click();

        expect(document.getElementById('imageModal').style.display).toBe('flex');
        expect(document.getElementById('imageModalImage').src).toContain('quiz-1.jpg');

        closeImageModal();
        expect(document.getElementById('imageModal').style.display).toBe('none');
    });

    it('preloads the full-resolution image when wiring a thumbnail', function () {
        var preloadedImage = { src: '' };
        spyOn(window, 'Image').and.returnValue(preloadedImage);

        wireZoomableImage(
            document.getElementById('image1'),
            'https://example.com/quiz-1_small.webp',
            'Destination image 1'
        );

        expect(preloadedImage.src).toBe('https://example.com/quiz-1.jpg');
    });

    it('opens a result image in a modal when clicked', function () {
        renderImageGallery(
            document.getElementById('resultsImages'),
            ['https://example.com/result-1_small.webp']
        );

        document.querySelector('#resultsImages .result-image').click();

        expect(document.getElementById('imageModal').style.display).toBe('flex');
        expect(document.getElementById('imageModalImage').src).toContain('result-1.jpg');
    });

    it('navigates between result images in the modal with arrow buttons', function () {
        renderImageGallery(
            document.getElementById('resultsImages'),
            [
                'https://example.com/result-1_small.webp',
                'https://example.com/result-2_small.webp'
            ]
        );

        document.querySelector('#resultsImages .result-image').click();

        expect(document.getElementById('imageModalPrevBtn').classList.contains('hidden')).toBeFalse();
        expect(document.getElementById('imageModalNextBtn').classList.contains('hidden')).toBeFalse();

        navigateImageModal(1);
        expect(document.getElementById('imageModalImage').src).toContain('result-2.jpg');

        navigateImageModal(-1);
        expect(document.getElementById('imageModalImage').src).toContain('result-1.jpg');
    });

    it('renders all result images without capping gallery size', function () {
        var urls = [];
        for (var i = 1; i <= 12; i += 1) {
            urls.push('https://example.com/result-' + i + '.jpg');
        }

        renderImageGallery(document.getElementById('resultsImages'), urls);

        expect(document.querySelectorAll('#resultsImages .result-image').length).toBe(12);
    });

    it('ignores duplicate result image URLs in the gallery', function () {
        renderImageGallery(
            document.getElementById('resultsImages'),
            [
                'https://example.com/result-1.jpg',
                'https://example.com/result-1.jpg',
                'https://example.com/result-2.jpg'
            ]
        );

        var images = document.querySelectorAll('#resultsImages .result-image');
        expect(images.length).toBe(2);
        expect(images[0].src).toContain('result-1.jpg');
        expect(images[1].src).toContain('result-2.jpg');
    });

    it('renders result images on the results screen shown after quiz completion', function () {
        showResults(true, 15, 'Bhutan', ['https://example.com/result-1.jpg']);

        var images = document.querySelectorAll('#resultsImages .quiz-image');
        expect(images.length).toBe(1);
        expect(images[0].src).toContain('result-1.jpg');
        expect(document.getElementById('resultsImages').classList.contains('hidden')).toBeFalse();
        expect(document.getElementById('resultsImagesHeading').textContent)
            .toBe('Here are all the pictures from Bhutan, as well as some bonus pictures');
        expect(document.getElementById('resultsImagesHeading').classList.contains('hidden')).toBeFalse();
        expect(document.querySelector('#resultsDetails .points-earned').textContent).toBe('15 Points!');
    });

    it('renders all destination hints on the results screen', function () {
        showResults(true, 15, 'Bhutan', [], {
            destinationHints: [
                { difficulty: 5, text: 'Highest level hint' },
                { difficulty: 4, text: 'Next level hint' },
                { difficulty: 3, text: '<script>not markup</script>' }
            ]
        });

        var review = document.getElementById('resultsHintReview');
        var items = document.querySelectorAll('#resultsHintReview li');

        expect(review.classList.contains('hidden')).toBeFalse();
        expect(items.length).toBe(3);
        expect(items[0].querySelector('.results-hint-label').textContent).toBe('First hint');
        expect(items[0].querySelector('p').textContent).toBe('Highest level hint');
        expect(items[2].querySelector('p').textContent).toBe('<script>not markup</script>');
        expect(review.querySelector('script')).toBeNull();
    });

    it('marks hint images as portrait when natural dimensions are portrait', function () {
        wireZoomableImage(
            document.getElementById('image1'),
            'https://example.com/portrait.jpg',
            'Destination image 1'
        );

        var image = document.getElementById('image1');
        Object.defineProperty(image, 'naturalWidth', { configurable: true, value: 600 });
        Object.defineProperty(image, 'naturalHeight', { configurable: true, value: 900 });
        image.dispatchEvent(new Event('load'));

        expect(image.classList.contains('is-portrait')).toBeTrue();
        expect(image.classList.contains('is-landscape')).toBeFalse();
    });

    it('uses portrait modal viewport for portrait images', function () {
        openImageModal('https://example.com/portrait-modal.jpg', 'Portrait image');

        var image = document.getElementById('imageModalImage');
        var card = document.querySelector('#imageModal .image-modal-card');
        Object.defineProperty(image, 'naturalWidth', { configurable: true, value: 700 });
        Object.defineProperty(image, 'naturalHeight', { configurable: true, value: 1100 });
        image.dispatchEvent(new Event('load'));

        expect(card.classList.contains('is-portrait')).toBeTrue();
        expect(card.classList.contains('is-landscape')).toBeFalse();
    });

    it('keeps desktop magnification active until a second click disables it', function () {
        openImageModal('https://example.com/modal.jpg', 'Modal image');

        var media = document.getElementById('imageModalMedia');
        var image = document.getElementById('imageModalImage');
        spyOn(media, 'getBoundingClientRect').and.returnValue({
            left: 0,
            top: 0,
            width: 400,
            height: 300
        });
        spyOn(media, 'setPointerCapture');

        media.dispatchEvent(new PointerEvent('pointerdown', {
            pointerId: 1,
            pointerType: 'mouse',
            button: 0,
            clientX: 100,
            clientY: 150
        }));

        expect(media.classList.contains('is-magnified')).toBeTrue();
        expect(image.style.getPropertyValue('--image-magnification')).toBe('6');
        expect(image.style.getPropertyValue('--image-magnification-origin')).toBe('25% 50%');

        media.dispatchEvent(new PointerEvent('pointerup', {
            pointerId: 1,
            pointerType: 'mouse'
        }));

        expect(media.classList.contains('is-magnified')).toBeTrue();
        expect(image.style.getPropertyValue('--image-magnification')).toBe('6');

        media.dispatchEvent(new PointerEvent('pointerdown', {
            pointerId: 2,
            pointerType: 'mouse',
            button: 0,
            clientX: 100,
            clientY: 150
        }));
        media.dispatchEvent(new PointerEvent('pointerup', {
            pointerId: 2,
            pointerType: 'mouse'
        }));

        expect(media.classList.contains('is-magnified')).toBeFalse();
        expect(image.style.getPropertyValue('--image-magnification')).toBe('');
    });

    it('disables native browser dragging for the enlarged image', function () {
        openImageModal('https://example.com/modal.jpg', 'Modal image');

        var image = document.getElementById('imageModalImage');
        var dragEvent = new Event('dragstart', { cancelable: true });

        image.dispatchEvent(dragEvent);

        expect(image.draggable).toBeFalse();
        expect(dragEvent.defaultPrevented).toBeTrue();
    });

    it('pans a magnified image by dragging with the mouse', function () {
        openImageModal('https://example.com/modal.jpg', 'Modal image');

        var media = document.getElementById('imageModalMedia');
        var image = document.getElementById('imageModalImage');
        Object.defineProperty(image, 'offsetWidth', { configurable: true, value: 400 });
        Object.defineProperty(image, 'offsetHeight', { configurable: true, value: 300 });
        spyOn(media, 'getBoundingClientRect').and.returnValue({
            left: 0,
            top: 0,
            width: 400,
            height: 300
        });
        spyOn(media, 'setPointerCapture');

        media.dispatchEvent(new PointerEvent('pointerdown', {
            pointerId: 1,
            pointerType: 'mouse',
            button: 0,
            clientX: 100,
            clientY: 150
        }));
        media.dispatchEvent(new PointerEvent('pointerup', {
            pointerId: 1,
            pointerType: 'mouse'
        }));
        media.dispatchEvent(new PointerEvent('pointerdown', {
            pointerId: 2,
            pointerType: 'mouse',
            button: 0,
            clientX: 100,
            clientY: 150
        }));
        media.dispatchEvent(new PointerEvent('pointermove', {
            pointerId: 2,
            pointerType: 'mouse',
            clientX: 180,
            clientY: 190
        }));
        media.dispatchEvent(new PointerEvent('pointerup', {
            pointerId: 2,
            pointerType: 'mouse'
        }));

        expect(image.style.getPropertyValue('--image-pan-x')).toBe('80px');
        expect(image.style.getPropertyValue('--image-pan-y')).toBe('40px');
        expect(image.style.getPropertyValue('--image-magnification')).toBe('6');
        expect(media.classList.contains('is-magnified')).toBeTrue();
    });

    it('preserves pinch magnification after touch pointers are released', function () {
        openImageModal('https://example.com/modal.jpg', 'Modal image');

        var media = document.getElementById('imageModalMedia');
        var image = document.getElementById('imageModalImage');
        spyOn(media, 'getBoundingClientRect').and.returnValue({
            left: 0,
            top: 0,
            width: 400,
            height: 300
        });
        spyOn(media, 'setPointerCapture');

        function dispatchTouchPointer(type, pointerId, clientX, clientY) {
            var event = new Event(type);
            Object.defineProperties(event, {
                pointerId: { value: pointerId },
                pointerType: { value: 'touch' },
                clientX: { value: clientX },
                clientY: { value: clientY }
            });
            media.dispatchEvent(event);
        }

        dispatchTouchPointer('pointerdown', 1, 100, 150);
        dispatchTouchPointer('pointerdown', 2, 200, 150);
        dispatchTouchPointer('pointermove', 2, 300, 150);

        expect(image.style.getPropertyValue('--image-magnification')).toBe('2');

        dispatchTouchPointer('pointerup', 2, 300, 150);
        dispatchTouchPointer('pointerup', 1, 100, 150);

        expect(media.classList.contains('is-magnified')).toBeTrue();
        expect(image.style.getPropertyValue('--image-magnification')).toBe('2');
    });

    it('pans a magnified image with one touch pointer', function () {
        openImageModal('https://example.com/modal.jpg', 'Modal image');

        var media = document.getElementById('imageModalMedia');
        var image = document.getElementById('imageModalImage');
        Object.defineProperty(image, 'offsetWidth', { configurable: true, value: 400 });
        Object.defineProperty(image, 'offsetHeight', { configurable: true, value: 300 });
        spyOn(media, 'setPointerCapture');

        function dispatchTouchPointer(type, pointerId, clientX, clientY) {
            var event = new Event(type);
            Object.defineProperties(event, {
                pointerId: { value: pointerId },
                pointerType: { value: 'touch' },
                clientX: { value: clientX },
                clientY: { value: clientY }
            });
            media.dispatchEvent(event);
        }

        dispatchTouchPointer('pointerdown', 1, 100, 150);
        dispatchTouchPointer('pointerdown', 2, 200, 150);
        dispatchTouchPointer('pointermove', 2, 300, 150);
        dispatchTouchPointer('pointerup', 2, 300, 150);
        dispatchTouchPointer('pointermove', 1, 180, 190);

        expect(image.style.getPropertyValue('--image-pan-x')).toBe('80px');
        expect(image.style.getPropertyValue('--image-pan-y')).toBe('40px');
    });
});