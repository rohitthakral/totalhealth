{
  "name"                 :  "Invoice Customization",
  "summary"              :  """Odoo Invoice Customization.""",
  "category"             :  "Account",
  "version"              :  "1.0.4",
  "sequence"             :  1,
  "author"               :  "Target Integration.",
  "website"              :  "http://www.targetintegration.com",
  "description"          :  """Invoice Customization""",
  "depends"              :  [
                             'sale_management',
                             'stock',
                            ],
  "data"                 :  [
                              'views/inherit_product.xml',
                            ],
  "application"          :  True,
  "installable"          :  True,
  "auto_install"         :  False,
}