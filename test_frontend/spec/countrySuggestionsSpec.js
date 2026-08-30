describe('Country answer suggestions', function () {
    var answerInput;

    beforeEach(function () {
        answerInput = document.getElementById('answerInput');
        answerInput.removeAttribute('list');
        document.getElementById('countryAnswerSuggestions')?.remove();
    });

    afterEach(function () {
        answerInput.removeAttribute('list');
        document.getElementById('countryAnswerSuggestions')?.remove();
    });

    it('offers all UN member states for country quizzes', function () {
        updateAnswerSuggestions('countries');

        var suggestions = document.getElementById('countryAnswerSuggestions');
        expect(answerInput.getAttribute('list')).toBe('countryAnswerSuggestions');
        expect(suggestions.options.length).toBe(193);
        expect(Array.from(suggestions.options, option => option.value)).toContain('Bhutan');
        expect(Array.from(suggestions.options, option => option.value)).toContain('Zimbabwe');
    });

    it('removes country suggestions for other quiz types', function () {
        updateAnswerSuggestions('countries');
        updateAnswerSuggestions('cities');

        expect(answerInput.hasAttribute('list')).toBe(false);
        expect(document.getElementById('countryAnswerSuggestions')).toBeNull();
    });
});