create table allergen (
    id      bigint      generated always as identity primary key,
    name    text        not null unique
);

create table ingredient (
    id      bigint      generated always as identity primary key,
    name    text        not null unique
);

-- Join table
create table ingredient_allergen (
    ingredient_id   bigint    not null references ingredient(id)  on delete cascade,
    allergen_id     bigint    not null references allergen(id)  on delete cascade,
    primary key (ingredient_id, allergen_id)
);

create table recipe (
    id  bigint generated always as identity primary key,
    title   text not null,
    source_url text
);

create table recipe_ingredient (
    recipe_id   bigint not null references recipe(id)   on delete cascade,
    ingredient_id bigint not null references ingredient(id) on delete cascade,
    amount      text,
    primary key (recipe_id, ingredient_id)
);

create table product (
    id  bigint generated always as identity primary key,
    barcode text unique,
    name    text not null,
    data_source text,
    last_checked date
);

create table product_allergen (
    product_id  bigint not null references product(id) on delete cascade,
    allergen_id bigint not null references allergen(id) on delete cascade,
    level       text not null check (level in ('contains', 'may contain')), --assuming 'contains' and 'may contain' are the best ways to check this
    primary key (product_id, allergen_id)
);

create table restaurant (
    id      bigint  generated always as identity primary key,
    name    text    not null
);

create table menu_item (
    id              bigint generated always as identity primary key,
    restaurant_id   bigint not null references restaurant(id) on delete cascade,
    name            text not null,
    price           numeric(9, 2), --up to 9999999.99
    data_source     text,
    last_checked    date
);

create table menu_item_allergen (
    menu_item_id    bigint not null references menu_item(id) on delete cascade,
    allergen_id     bigint not null references allergen(id)  on delete cascade,
    level           text not null check (level in ('contains', 'may contain')),
    primary key (menu_item_id, allergen_id)
);