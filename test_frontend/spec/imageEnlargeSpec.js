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
            '<div id="feedbackScreen" class="screen hidden">' +
                '<div id="feedbackStatus"></div>' +
                '<div id="feedbackDetails"></div>' +
                '<h3 id="feedbackResultImagesHeading" class="hidden"></h3>' +
                '<div id="feedbackResultImages" class="images-section hidden"></div>' +
            '</div>' +
            '<div id="resultsScreen" class="screen hidden">' +
                '<span id="finalScore"></span>' +
                '<p id="resultsMessage"></p>' +
            '</div>' +
            '<div id="resultImages" class="result-images hidden"></div>' +
            '<div id="imageModal" class="modal-overlay" style="display:none;" role="dialog" aria-modal="true" aria-label="Enlarged image">' +
                '<div class="modal-card image-modal-card">' +
                    '<button id="imageModalPrevBtn" type="button" class="image-modal-nav image-modal-nav-prev" aria-label="Show previous hint image">&#8249;</button>' +
                    '<button id="imageModalNextBtn" type="button" class="image-modal-nav image-modal-nav-next" aria-label="Show next hint image">&#8250;</button>' +
                    '<button id="imageModalCloseBtn" type="button" class="image-modal-close" aria-label="Close enlarged image">×</button>' +
                    '<img id="imageModalImage" src="" alt="" class="image-modal-image">' +
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

    it('opens a result image in a modal when clicked', function () {
        renderResultImages(['https://example.com/result-1.jpg']);

        document.querySelector('#resultImages .result-image').click();

        expect(document.getElementById('imageModal').style.display).toBe('flex');
        expect(document.getElementById('imageModalImage').src).toContain('result-1.jpg');
    });

    it('navigates between result images in the modal with arrow buttons', function () {
        renderResultImages([
            'https://example.com/result-1.jpg',
            'https://example.com/result-2.jpg'
        ]);

        document.querySelector('#resultImages .result-image').click();

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

        renderResultImages(urls);

        expect(document.querySelectorAll('#resultImages .result-image').length).toBe(12);
    });

    it('renders result images on the feedback screen shown after quiz completion', function () {
        showFeedback(true, 15, 'Bhutan', ['https://example.com/result-1.jpg']);

        var images = document.querySelectorAll('#feedbackResultImages .quiz-image');
        expect(images.length).toBe(1);
        expect(images[0].src).toContain('result-1.jpg');
        expect(document.getElementById('feedbackResultImages').classList.contains('hidden')).toBeFalse();
        expect(document.getElementById('feedbackResultImagesHeading').textContent)
            .toBe('Here are some extra pictures from Bhutan');
        expect(document.getElementById('feedbackResultImagesHeading').classList.contains('hidden')).toBeFalse();
        expect(document.querySelector('#feedbackDetails .points-earned').textContent).toBe('15 Points!');
    });

    it('includes all unlocked hint images in the end-result gallery', function () {
        quizState.unlockedHintDifficulties = [5, 4, 3];
        quizState.hintImagesByDifficulty = {
            5: ['https://example.com/h5a.jpg', 'https://example.com/h5b.jpg'],
            4: ['https://example.com/h4a.jpg', 'https://example.com/h4b.jpg'],
            3: ['https://example.com/h3a.jpg', 'https://example.com/h3b.jpg']
        };

        showFeedback(true, 15, 'Bhutan', ['https://example.com/result-1.jpg']);
        endQuiz();

        var images = document.querySelectorAll('#resultImages .result-image');
        expect(images.length).toBe(7);
        expect(Array.from(images).map(function (img) { return img.src; })).toEqual([
            'https://example.com/result-1.jpg',
            'https://example.com/h5a.jpg',
            'https://example.com/h5b.jpg',
            'https://example.com/h4a.jpg',
            'https://example.com/h4b.jpg',
            'https://example.com/h3a.jpg',
            'https://example.com/h3b.jpg'
        ]);
    });

    it('keeps hint images in end-result gallery even if live hint state is cleared', function () {
        quizState.unlockedHintDifficulties = [5, 4];
        quizState.hintImagesByDifficulty = {
            5: ['https://example.com/h5a.jpg', 'https://example.com/h5b.jpg'],
            4: ['https://example.com/h4a.jpg', 'https://example.com/h4b.jpg']
        };

        showFeedback(true, 15, 'Bhutan', ['https://example.com/result-1.jpg']);

        // Simulate state being reset before navigating to the end results screen.
        quizState.unlockedHintDifficulties = [];
        quizState.hintImagesByDifficulty = {};

        endQuiz();

        var images = document.querySelectorAll('#resultImages .result-image');
        expect(images.length).toBe(5);
        expect(Array.from(images).map(function (img) { return img.src; })).toEqual([
            'https://example.com/result-1.jpg',
            'https://example.com/h5a.jpg',
            'https://example.com/h5b.jpg',
            'https://example.com/h4a.jpg',
            'https://example.com/h4b.jpg'
        ]);
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
});