import { createRouter, createWebHistory } from 'vue-router'
import SanityPage from '@/components/sanity/Sanity.vue'
import HomePage from '@/components/homepage/HomePage.vue'
import ProjectPage from '@/components/project/ProjectPage.vue'
import JobForm from '@/components/homepage/JobForm.vue'
import SanityHomePage from '@/components/sanity/SanityHomePage.vue'
import PatientPage from '@/components/project/PatientPage.vue'
import ProtectedPage from '@/components/ProtectedPage.vue'
import storageHelper from 'storage-helper'
import PatientPredictions from '@/components/sanity/PatientPredictions.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomePage,
      meta: {
        requiresAuth:true
      }
    },
    {
      path:'/submit_job',
      name: 'submit_job',
      component: JobForm,
      meta: {
        requiresAuth:true
      }
    },
    {
      path: '/:project',
      name: 'project',
      component: ProjectPage,
      meta: {
        requiresAuth:true
      }
    },
    {
      path: '/:project/sanity',
      name: 'sanityHomePage',
      component: SanityHomePage,
      meta: {
        requiresAuth:true
      }
    },
    {
      path: '/:project/sanity/:vertebra',
      name: 'sanity',
      component: SanityPage,
      meta: {
        requiresAuth:true
      }
    },
    {
      path: '/:project/weights/:patientID',
      name: 'patientPage',
      component: PatientPage,
      meta: {
        requiresAuth:true
      }
    },
    {
      path: '/:project/patient_qa/:vertebra/:patient_id?',
      name: 'patientPredictions',
      component: PatientPredictions,
      meta: {
        requiresAuth:true
      }
    },
    {
      path: '/protected',
      name: 'protected',
      component: ProtectedPage,
      meta: {
        requiresAuth:false
      }
    }
  ]
})

export default router

router.beforeEach((to, from, next) => {
  if (to.meta.requiresAuth) {
    if (!storageHelper.getItem('user-password')) next('/protected')
    else next()
  } else next()
})