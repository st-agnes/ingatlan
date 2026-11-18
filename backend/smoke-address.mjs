/** Explicit fictional addresses accepted only by the opt-in development/TEST geocoder. */
export function withTestAddress(path, method, body) {
  if (!body || !['POST', 'PUT'].includes(method) || !/^\/properties(?:\/[^/]+)?$/.test(path)) return body;
  return {
    ...body,
    ...(!Object.hasOwn(body, 'street') ? {street: 'OTTHONRA TEST'} : {}),
    ...(!Object.hasOwn(body, 'houseNumber') ? {houseNumber: '1'} : {}),
    ...(!Object.hasOwn(body, 'postalCode') ? {postalCode: null} : {})
  };
}
