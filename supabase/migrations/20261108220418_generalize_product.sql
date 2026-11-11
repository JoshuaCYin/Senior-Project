alter table product rename column off_allergen_tags to allergen_tags;
alter table product rename column off_trace_tags    to trace_tags;
alter table product rename column off_last_modified to source_last_modified;
alter table product rename column completeness to data_completeness;
alter table product add column category_tags text[];

alter table product drop constraint product_barcode_key;
alter table product add constraint product_source_barcode_key unique (data_source, barcode);

create table allergen_rule (
  id          bigint generated always as identity primary key,
  allergen_id bigint not null references allergen(id) on delete cascade,
  source      text   not null,                                  -- 'Open Food Facts'
  pattern     text   not null,                                  -- '%whey%'
  kind        text   not null check (kind in ('include', 'exclude'))
);