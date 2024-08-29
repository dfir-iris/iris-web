// ***********************************************
// This example commands.js shows you how to
// create various custom commands and overwrite
// existing commands.
//
// For more comprehensive examples of custom
// commands please read more here:
// https://on.cypress.io/custom-commands
// ***********************************************
//
//
Cypress.Commands.add('login', (username, password) => {
// TODO should cache, see https://docs.cypress.io/guides/end-to-end-testing/testing-your-app#Improving-performance
    cy.visit('/')
    // which one is better? Both would work...
    //cy.get('#username')
    cy.get('input[name=username]').type('administrator')
    cy.get('input[name=password]').type(`${password}{enter}`)
})

Cypress.Commands.add('login_administrator', () => {
    cy.login('administrator', 'MySuperAdminPassword!')
})
