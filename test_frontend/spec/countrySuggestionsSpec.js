describe('Country answer suggestions', function () {
    var answerInput;
    var originalFetch;
    var mockCountriesText = [
        'Afghanistan', 'Albania', 'Algeria', 'Andorra', 'Angola', 'Antigua and Barbuda',
        'Argentina', 'Armenia', 'Australia', 'Austria', 'Azerbaijan', 'Bahamas', 'Bahrain',
        'Bangladesh', 'Barbados', 'Belarus', 'Belgium', 'Belize', 'Benin', 'Bhutan',
        'Bolivia', 'Bosnia and Herzegovina', 'Botswana', 'Brazil', 'Brunei', 'Bulgaria',
        'Burkina Faso', 'Burundi', 'Cabo Verde', 'Cambodia', 'Cameroon', 'Canada',
        'Central African Republic', 'Chad', 'Chile', 'China', 'Colombia', 'Comoros',
        'Congo', 'Costa Rica', "Cote d'Ivoire", 'Croatia', 'Cuba', 'Cyprus', 'Czechia',
        'Democratic Republic of the Congo', 'Denmark', 'Djibouti', 'Dominica',
        'Dominican Republic', 'Ecuador', 'Egypt', 'El Salvador', 'Equatorial Guinea',
        'Eritrea', 'Estonia', 'Eswatini', 'Ethiopia', 'Fiji', 'Finland', 'France', 'Gabon',
        'Gambia', 'Georgia', 'Germany', 'Ghana', 'Greece', 'Grenada', 'Guatemala', 'Guinea',
        'Guinea-Bissau', 'Guyana', 'Haiti', 'Honduras', 'Hungary', 'Iceland', 'India',
        'Indonesia', 'Iran', 'Iraq', 'Ireland', 'Israel', 'Italy', 'Jamaica', 'Japan',
        'Jordan', 'Kazakhstan', 'Kenya', 'Kiribati', 'Kuwait', 'Kyrgyzstan', 'Laos', 'Latvia',
        'Lebanon', 'Lesotho', 'Liberia', 'Libya', 'Liechtenstein', 'Lithuania', 'Luxembourg',
        'Madagascar', 'Malawi', 'Malaysia', 'Maldives', 'Mali', 'Malta', 'Marshall Islands',
        'Mauritania', 'Mauritius', 'Mexico', 'Micronesia', 'Moldova', 'Monaco', 'Mongolia',
        'Montenegro', 'Morocco', 'Mozambique', 'Myanmar', 'Namibia', 'Nauru', 'Nepal',
        'Netherlands', 'New Zealand', 'Nicaragua', 'Niger', 'Nigeria', 'North Korea',
        'North Macedonia', 'Norway', 'Oman', 'Pakistan', 'Palau', 'Panama',
        'Papua New Guinea', 'Paraguay', 'Peru', 'Philippines', 'Poland', 'Portugal', 'Qatar',
        'Romania', 'Russia', 'Rwanda', 'Saint Kitts and Nevis', 'Saint Lucia',
        'Saint Vincent and the Grenadines', 'Samoa', 'San Marino', 'Sao Tome and Principe',
        'Saudi Arabia', 'Senegal', 'Serbia', 'Seychelles', 'Sierra Leone', 'Singapore',
        'Slovakia', 'Slovenia', 'Solomon Islands', 'Somalia', 'South Africa', 'South Korea',
        'South Sudan', 'Spain', 'Sri Lanka', 'Sudan', 'Suriname', 'Sweden', 'Switzerland',
        'Syria', 'Tajikistan', 'Tanzania', 'Thailand', 'Timor-Leste', 'Togo', 'Tonga',
        'Trinidad and Tobago', 'Tunisia', 'Turkey', 'Turkmenistan', 'Tuvalu', 'Uganda',
        'Ukraine', 'United Arab Emirates', 'United Kingdom', 'United States', 'Uruguay',
        'Uzbekistan', 'Vanuatu', 'Venezuela', 'Vietnam', 'Yemen', 'Zambia', 'Zimbabwe'
    ].join('\n');

    beforeEach(function () {
        originalFetch = window.fetch;
        spyOn(window, 'fetch').and.callFake(function (url) {
            if (typeof url === 'string' && url.includes('countries.txt')) {
                return Promise.resolve({
                    ok: true,
                    text: function () {
                        return Promise.resolve(mockCountriesText);
                    }
                });
            }
            return Promise.resolve({
                ok: false,
                status: 404
            });
        });

        answerInput = document.getElementById('answerInput');
        answerInput.removeAttribute('list');
        answerInput.value = '';
        document.getElementById('countryAnswerSuggestions')?.remove();
        countryNamesCache = null;
    });

    afterEach(function () {
        answerInput.removeAttribute('list');
        answerInput.value = '';
        document.getElementById('countryAnswerSuggestions')?.remove();
        countryNamesCache = null;
        window.fetch = originalFetch;
    });

    it('offers all UN member states for country quizzes', async function () {
        await updateAnswerSuggestions('countries');

        var suggestions = document.getElementById('countryAnswerSuggestions');
        expect(answerInput.getAttribute('list')).toBe('countryAnswerSuggestions');
        expect(suggestions.options.length).toBe(193);
        expect(Array.from(suggestions.options, option => option.value)).toContain('Bhutan');
        expect(Array.from(suggestions.options, option => option.value)).toContain('Zimbabwe');
    });

    it('removes country suggestions for other quiz types', async function () {
        await updateAnswerSuggestions('countries');
        await updateAnswerSuggestions('cities');

        expect(answerInput.hasAttribute('list')).toBe(false);
        expect(document.getElementById('countryAnswerSuggestions')).toBeNull();
    });

    it('matches substrings when typing so typing congo matches Democratic Republic of the Congo', async function () {
        await updateAnswerSuggestions('countries');

        var suggestions = document.getElementById('countryAnswerSuggestions');
        answerInput.value = 'congo';
        answerInput.dispatchEvent(new Event('input'));

        var values = Array.from(suggestions.options, option => option.value);
        expect(values).toContain('Congo');
        expect(values).toContain('Democratic Republic of the Congo');
        expect(values.length).toBe(2);
    });
});