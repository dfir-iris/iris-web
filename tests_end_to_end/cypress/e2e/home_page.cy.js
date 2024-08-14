describe('The Home Page', () => {
    it('successfully loads', () => {
        cy.login_administrator()
        // TODO should we
        //      introduce a data-cy attribute https://docs.cypress.io/guides/references/best-practices#Selecting-Elements,
        //      or use aria https://playwright.dev/python/docs/locators?
        cy.contains('Create new case').click()
        cy.get('#submit_new_case_btn').click()

        // which one is better among the 3 following? (less brittle)
        cy.contains('Invalid data type')
        cy.get('#case_customer-invalid-msg')
        cy.get('#case_customer-invalid-msg').should('have.text', 'Invalid data type')
    })
})