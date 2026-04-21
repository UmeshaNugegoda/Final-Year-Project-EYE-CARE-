import React from 'react'
import { Search } from 'lucide-react'
import './Header.css'

/**
 * PageHeader — the in-page title row that appears below the top nav.
 *
 * Props:
 *  title       — big h1 heading (required)
 *  subtitle    — small description line below title
 *  searchValue — controlled value for the optional search input
 *  onSearch    — onChange callback for the search input
 *  searchPlaceholder — placeholder text (default "Search here...")
 *  action      — { label, onClick } for an optional CTA button on the right
 */
function Header({ title, subtitle, searchValue, onSearch, searchPlaceholder, action }) {
  return (
    <div className="page-header">
      <div className="page-header-left">
        <h1 className="page-header-title">{title}</h1>
        {subtitle && <p className="page-header-subtitle">{subtitle}</p>}
      </div>

      {(onSearch || action) && (
        <div className="page-header-right">
          {onSearch && (
            <div className="page-header-search">
              <Search size={15} className="page-header-search-icon" />
              <input
                type="text"
                className="page-header-search-input"
                placeholder={searchPlaceholder || 'Search here...'}
                value={searchValue || ''}
                onChange={onSearch}
                aria-label="Search"
              />
            </div>
          )}
          {action && (
            <button
              type="button"
              className={`page-header-action-btn${action.className ? ` ${action.className}` : ''}`}
              onClick={action.onClick}
            >
              {action.icon && <span className="page-header-action-icon">{action.icon}</span>}
              {action.label}
            </button>
          )}
        </div>
      )}
    </div>
  )
}

export default Header
