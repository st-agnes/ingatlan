/** Hungarian energy-performance certificate classes used since 2023-11-01.
 * Source: 176/2008. (VI. 30.) Korm. rendelet, Appendix 3; e-epites.hu.
 * Older schemes are deliberately not inferred from their letter labels.
 */
export const ENERGY_RATING_SCHEME = '2023';
export const ENERGY_RATINGS = Object.freeze(['I','H','G','F','E','D','C','B','A','A+','A++','A+++']);
export const ENERGY_COLORS = Object.freeze({
  '':'#ffffff', I:'#222222', H:'#79512f', G:'#92283c', F:'#d44235', E:'#ef8c30',
  D:'#f3d741', C:'#bdcf39', B:'#87bb3d', A:'#64af55', 'A+':'#39994d', 'A++':'#18843e', 'A+++':'#09682d'
});
export const ENERGY_RATING_OPTIONS = Object.freeze(ENERGY_RATINGS.map(value=>Object.freeze({value,label:value,color:ENERGY_COLORS[value]})));
export const ENERGY_SLIDER_OPTIONS = Object.freeze([Object.freeze({value:'',label:'Nincs megadva',color:ENERGY_COLORS['']}),...ENERGY_RATING_OPTIONS]);
export const energyIndex = value => ENERGY_RATINGS.indexOf(typeof value==='string'?value.trim().toUpperCase():'');
export const energySliderIndex = (value,scheme=ENERGY_RATING_SCHEME) => scheme===ENERGY_RATING_SCHEME ? energyIndex(value)+1 : 0;
export const energyCode = value => energyIndex(value)<0?'':ENERGY_RATINGS[energyIndex(value)];
export const knownEnergyRating = value => value?.energyRatingScheme===ENERGY_RATING_SCHEME ? energyIndex(value.energyRating) : -1;
export const meetsEnergyMinimum = (property,minimum) => energyIndex(minimum)<0 || knownEnergyRating(property)>=energyIndex(minimum);
