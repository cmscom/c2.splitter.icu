# Changelog

<!--
   You should *NOT* be adding new change log entries to this file.
   You should create a file in the news directory instead.
   For helpful instructions, please see:
   https://github.com/plone/plone.releaser/blob/master/ADD-A-NEWS-ITEM.rst
-->

<!-- towncrier release notes start -->

## 1.0.0b1 (2026-10-20)


### New features:

- Initial release: a ZCTextIndex word splitter that splits text at ICU word boundaries ("ICU word splitter"), an optional `c2.splitter.icu:evaluation` profile that adds `icu_lexicon` and `SearchableText_icu` next to `SearchableText`, and a `@@icu-compare` view for managers to compare both indexes. [terapyon] 
- The ICU word splitter takes its locale from the site language (`plone.default_language`) when its lexicon is made, and keeps it; without a site, or with a language ICU does not know, the locale is `ja`. `@@icu-compare` shows the locale of `icu_lexicon`. [terapyon]
