import crypto from 'node:crypto';

const createCase = async (rest) => {
    const caseName = `Case - ${crypto.randomUUID()}`;

    // TODO maybe should remove cases between each tests (like in the backend tests)
    const response = await rest.post('/api/v2/cases', {
        data: {
            case_name: caseName,
            case_description: 'Case description',
            case_customer: 1,
            case_soc_id: ''
        }
    });
    return (await response.json()).case_id;
};

export default {
    createCase
}