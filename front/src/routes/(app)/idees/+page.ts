import { resoudreOnglet } from '$lib/deepLink';

//  Les trois rubriques de la Communauté sont des CONTENUS : elles ont donc une
//  adresse de premier niveau (`/annonces`), et non un segment sous la page. La
//  contrepartie est ces trois routes jumelles — SvelteKit n'a pas d'autre façon
//  de faire répondre un même écran à trois chemins sans les rendre paramétrés,
//  ce qui redonnerait `/communaute/annonces`.
export const load = ({ url }) => resoudreOnglet('communaute', url);
