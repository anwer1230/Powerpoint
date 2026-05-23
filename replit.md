# Photo Management Application

## Overview

This is a full-stack photo management web application built with a modern tech stack. The application allows users to upload, organize, and manage photos in albums, create memories with templates, and share them socially. It features a React frontend with a clean, modern UI using shadcn/ui components and an Express.js backend with PostgreSQL database integration.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Framework**: React 18 with TypeScript
- **Routing**: Wouter for client-side routing
- **State Management**: TanStack Query (React Query) for server state management
- **UI Components**: shadcn/ui component library built on Radix UI primitives
- **Styling**: Tailwind CSS with CSS custom properties for theming
- **Build Tool**: Vite for fast development and optimized builds

### Backend Architecture
- **Framework**: Express.js with TypeScript
- **Database ORM**: Drizzle ORM with PostgreSQL
- **File Handling**: Multer for multipart file uploads with Sharp for image processing
- **Session Management**: Connect-pg-simple for PostgreSQL session storage
- **Development**: Hot Module Replacement (HMR) with Vite integration

### Project Structure
- `client/` - React frontend application
- `server/` - Express.js backend API
- `shared/` - Shared TypeScript schemas and types
- `uploads/` - File storage directory for uploaded photos

## Key Components

### Database Schema
The application uses three main entities:
- **Photos**: Store image metadata, tags, album associations, and file information
- **Albums**: Organize photos into collections with custom colors and descriptions
- **Memories**: Template-based photo compositions for sharing

### API Endpoints
- `GET/POST /api/photos` - Photo management with filtering by album and tags
- `POST /api/photos/upload` - Multi-file photo upload with image processing
- `GET/POST /api/albums` - Album creation and retrieval
- `GET/POST /api/memories` - Memory template management

### Frontend Components
- **PhotoGrid**: Responsive grid layout for photo display with selection capabilities
- **Sidebar**: Navigation and album management interface
- **UploadDropzone**: Drag-and-drop file upload with progress tracking
- **MemoryCreationModal**: Template-based memory creation interface
- **SocialSharingModal**: Export and sharing functionality

## Data Flow

1. **Photo Upload**: Files are uploaded via multipart form data, processed with Sharp for optimization, and stored in the uploads directory
2. **Database Operations**: Drizzle ORM handles all database interactions with type-safe queries
3. **State Management**: TanStack Query manages API calls, caching, and optimistic updates
4. **Real-time Updates**: Query invalidation ensures UI stays synchronized with backend changes

## External Dependencies

### Core Dependencies
- **@neondatabase/serverless**: PostgreSQL database driver optimized for serverless environments
- **@tanstack/react-query**: Server state management and caching
- **drizzle-orm**: Type-safe database ORM with schema validation
- **multer & sharp**: File upload handling and image processing
- **wouter**: Lightweight React router

### UI Dependencies
- **@radix-ui/***: Unstyled, accessible UI primitives
- **tailwindcss**: Utility-first CSS framework
- **class-variance-authority**: Type-safe variant API for components
- **react-dropzone**: File drag-and-drop functionality

## Deployment Strategy

### Development
- Vite dev server with HMR for frontend development
- Express server with TypeScript compilation via tsx
- Environment-based configuration with DATABASE_URL

### Production Build
- Frontend: Vite builds optimized static assets to `dist/public`
- Backend: esbuild bundles server code to `dist/index.js`
- Database migrations managed via `drizzle-kit push`

### Environment Setup
- PostgreSQL database required (configured via DATABASE_URL)
- File system access for uploads directory
- Node.js environment with ES modules support

The application follows a monorepo structure with shared TypeScript types, enabling type safety across the full stack while maintaining clear separation between frontend and backend concerns.